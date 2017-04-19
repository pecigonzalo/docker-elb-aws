import os
import logging
import ConfigParser
from Queue import Queue
from threading import Thread

import click
import boto3
import docker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("controller")


def getContainer(container_id, docker_client):
    return docker_client.containers.get(container_id=container_id)


def getPorts(container):
    ports = container.attrs.get("NetworkSettings").get("Ports")
    # EG: (u'12312/tcp', [{u'HostIp': u'0.0.0.0', u'HostPort': u'1234'}])

    for mappings in ports.values():
        # EG: [{u'HostPort': u'1234', u'HostIp': u'0.0.0.0'}]
        # Check if the port is mapped
        if mappings is not None:
            for mapping in mappings:
                yield mapping


def createELBPort(port, elb_name, elb_client):
    elb_client.create_load_balancer_listeners(
        LoadBalancerName=elb_name,
        Listeners=[
            {
                'Protocol': 'TCP',
                'LoadBalancerPort': port,
                'InstanceProtocol': 'TCP',
                'InstancePort': port,
            },
        ]
    )


def destroyELBPort(port, elb_name, elb_client):
    elb_client.delete_load_balancer_listeners(
        LoadBalancerName=elb_name,
        LoadBalancerPorts=[
            port,
        ]
    )


def worker(worker_id, work_queue, elb_client, elb_config, docker_client):
    # Set debug format to log worker id
    logger.debug("Starting worker {}".format(worker_id))
    try:
        while True:
            event = work_queue.get()

            container_id = event.get("id")
            container = docker_client.containers.get(container_id=container_id)

            for mapping in getPorts(container):
                logger.debug("Container: {} Action: {} Mapping: {}".format(
                    container,
                    event.get("Action"),
                    mapping,
                ))

                elb_name = elb_config.get('main', mapping.get("HostIp"))
                port = mapping.get("HostPort")

                if event.get("Action") == "start":
                    logger.info("{}:AWS will add {} to {}".format(
                            worker_id, port,
                            elb_name
                        )
                    )
                    createELBPort(int(port), elb_name, elb_client)

                elif event.get("Action") == "kill":
                    logger.info("{}:AWS will remove {} to {}".format(
                            worker_id, port,
                            elb_name
                        )
                    )
                    destroyELBPort(int(port), elb_name, elb_client)
            work_queue.task_done()
    except Exception as e:
        logger.error(e)
        os._exit(1)
        pass


@click.command()
@click.option(
    '--workers',
    default=2,
    envvar='WORKERS',
    help='Number of worker threads.'
    )
@click.option(
    '--debug',
    default=False,
    envvar='DEBUG',
    help='Enable or disable debug loggin.'
    )
@click.option(
    '--region',
    default='',
    envvar='AWS_REGION',
    help='AWS Region to look for the ELB.'
    )
def run(workers, debug, region):
    if debug in ["True", "true", "1"]:
        logger.info("Enabling debug loggin")
        logger.setLevel(level=logging.DEBUG)
        logger.debug("Debug loggin enabled")

    elb_config = ConfigParser.RawConfigParser()
    elb_config.read(
        os.getenv('ELB_CONFIG', '/var/lib/docker/swarm/config.cfg')
    )

    docker_client = docker.from_env()
    elb_client = boto3.client('elb', region_name=region)
    work_queue = Queue()

    for i in range(workers):
        t = Thread(
                target=worker, args=(
                    i,
                    work_queue,
                    elb_client,
                    elb_config,
                    docker_client
                )
            )
        t.daemon = True
        t.start()

    filters = {
        'Type': 'container'
    }

    for event in docker_client.events(decode=True, filters=filters):
        logger.debug(
            "Action:{} Image:{}".format(event.get("Action"), event.get("id"))
        )
        action = event.get("Action")
        if action in ["start", "kill"]:
            work_queue.put(
                event
            )
        else:
            logger.debug("It did not match any 'start' or 'kill'")

    work_queue.join()  # block until all tasks are done


if __name__ == '__main__':
    run()
