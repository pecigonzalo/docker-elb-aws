docker run \
  --log-driver=json-file \
  --name=elb-aws \
  --restart=always \
  -d \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /var/lib/docker/swarm:/var/lib/docker/swarm \
  -e ELB_CONFIG=/var/lib/docker/swarm/elb.cfg \
  -e AWS_REGION=$AWS_REGION \
  -e DEBUG=True \
   pecigonzalo/docker-elb-aws
