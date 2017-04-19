import time
import logging
import ConfigParser

import click
import boto3
import docker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("controller")


def getServices(docker_client):
    return docker_client.services.list()


def getPorts(services):
    ports = []
    for service in services:
        service_ports = service.attrs.get("Endpoint").get("Ports")
        if service_ports:
            for service_port in service_ports:
                ports.append(
                    service_port
                )
    # EG:
    # [{u'Protocol': u'tcp',
    # u'PublishMode': u'ingress',
    # u'PublishedPort': 5000,
    # u'TargetPort': 80}]

    return ports
    # for port in ports:
    #     # EG: {u'TargetPort': 80, u'PublishedPort': 5000, u'Protocol': u'tcp', u'PublishMode': u'ingress'}
    #     yield port


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


def updateELB(elb_client, elb_config, ports):
    current_listeners = []
    current_services = []

    for port in ports:
        current_services.append(
            (
                int(port.get("PublishedPort")),
                str(port.get("Protocol").upper()),
            )
        )
    current_services = sorted(current_services)
    logger.debug('CurrentServices: {}'.format(current_services))

    # We dont support multipe load balancers yet so select default
    elb_name = elb_config.get('main', "default")

    listeners = elb_client.describe_load_balancers(
            LoadBalancerNames=[elb_name]
        ) \
        .get("LoadBalancerDescriptions")[0] \
        .get("ListenerDescriptions")  # Get Descriptions from array

    for listener in listeners:
        current_listeners.append(
            (
                int(listener.get("Listener").get("InstancePort")),
                str(listener.get("Listener").get("InstanceProtocol")),
            )
        )
    current_listeners = sorted(current_listeners)
    logger.debug('CurrentListeners: {}'.format(current_listeners))

    listeners_to_delete = list(set(current_listeners) - set(current_services))
    listeners_to_create = list(set(current_services) - set(current_listeners))

    if listeners_to_delete:
        logger.info('Starting to delete unnecessary listeners on ELB: {} ({} in total).'.format(
            elb_name, len(listeners_to_delete)))
        logger.debug('ToDelete: {}'.format(listeners_to_delete))
        for listener in listeners_to_delete:
            port = listener[0]
            destroyELBPort(port, elb_name, elb_client)
            time.sleep(0.2)
        logger.info('All unnecessary listeners deleted.')

    if listeners_to_create:
        logger.info('Starting to create missing listeners on ELB: {} ({} in total).'.format(
            elb_name, len(listeners_to_create)))
        logger.debug('ToCreate: {}'.format(listeners_to_create))
        for listener in listeners_to_create:
            port = listener[0]
            createELBPort(port, elb_name, elb_client)
            time.sleep(0.2)
        logger.info('All missing listeners created.')


@click.command()
@click.option(
    '--debug',
    default=False,
    envvar='DEBUG',
    help='Enable or disable debug loggin (default False).'
    )
@click.option(
    '--config',
    default='/var/lib/docker/swarm/config.cfg',
    envvar='ELB_CONFIG',
    help='Enable or disable debug loggin (default False).'
    )
@click.option(
    '--region',
    default='',
    envvar='AWS_REGION',
    help='AWS Region to look for the ELB.'
    )
@click.option(
    '--poll_interval',
    default=3,
    help='Polling interval in seconds (default 3).'
    )
def run(debug, config, region, poll_interval):
    if debug in ["True", "true", "1"]:
        logger.info("Enabling debug loggin")
        logger.setLevel(level=logging.DEBUG)
        logger.debug("Debug loggin enabled")

    elb_config = ConfigParser.RawConfigParser()
    elb_config.read(config)

    docker_client = docker.from_env()
    elb_client = boto3.client('elb', region_name=region)

    while True:
        node = docker_client.nodes.get(
            docker_client.info().get("Swarm").get("NodeID")
        )
        if node.attrs.get("ManagerStatus").get("Leader"):
            ports = getPorts(
                getServices(docker_client)
            )
            updateELB(
                elb_client,
                elb_config,
                ports
            )
        else:
            logger.warn("Node is not a Leader")

        time.sleep(poll_interval)


if __name__ == '__main__':
    run()
