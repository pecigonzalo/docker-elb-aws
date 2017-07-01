# Docker Swarm for AWS ELB Autoupdater

This container will poll the Docker Swarm cluster for all published ports and update the cluster ELB.

*Example project:* **[Terraform docker-swarm](https://github.com/pecigonzalo/tf-docker-swarm)**

### Description
Uses the docker python API to query the running stacks/services with published ports and updates the ELB to map those ports on it.

### Usage
##### Paramaters
| Parameter | Example | Description |
|-----------|:-------:|:------------|
| DEBUG | True | Enable debug logging |
| ELB_CONFIG | - | Path to a valid controller config file |
| AWS_REGION | eu-central-1 | AWS Region ID|
| POLL_INTERVAL | 3 | Time in seconds to sleep between polls |

##### WIP: Controller configuration
This configuration list the target ELB for each network and a default, this should add support for clusters present on multiple networks.

```
[main]
127.0.0.1: testELB-Name
0.0.0.0: testELB-Name
default: testELB-Name
```

##### Example
```
docker run -d \
  --name=elb-aws \
  --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /var/lib/docker/swarm:/var/lib/docker/swarm \
  -e ELB_CONFIG=/var/lib/docker/swarm/elb.cfg \
  -e AWS_REGION=$AWS_REGION \
  -e DEBUG=True \
   pecigonzalo/docker-elb-aws
```
