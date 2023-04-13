What
====
nft_tool.py is a script to read/parse docker-compose and update the configured nftable firewall.

Who
===
Docker (docker-compose specifically) users that want to use nft as their primary firewall and want more control over their security.

These docker users will likely have this configuration:

/etc/docker/daemon.json
```json
{
    "iptables":false,
    "userland-proxy": false
}
```

Users of my https://github.com/josefwells/make-compose interface might would want to point to NFT_TOOL to this.


Why
===
Docker uses iptables firewall rules not just for external access to those ports, but also to forward ports around docker networks.

When you turn off docker iptables, docker will instead try to run proxy-services for your port-forwards, think:

```yaml
ports:
 - 80:8080
```
When you connect to your docker host port 8080, you want it to be forwarded to the container, port 80.
You can see these processes with ps.

```bash
$ ps -ef|grep docker-proxy
root      5432   1234  0 16:20 ?  00:00:00 /usr/bin/docker-proxy -proto tcp -host-ip 0.0.0.0 -host-port 8080 -container-ip 172.17.0.2 -container-port 80
```
Well this is cool unless you are running docker on your router and a bunch of services on your router that you want to see internally by default, but not externally.
Now maybe I'm bad at networking (I am), but I couldn't figure out how to differentiate external access to these services from internal access because the proxied accesses \
were always from my host.

So I turned off userland-proxy.

So then I needed to proxy these with nft, which is exactly what this cool tool does.

How
===
nft_tool reads my docker_compose.yml
 - finds the network (assumes you only have one)
 - finds the service requested
 - finds the IP specified on the network it found
 - finds the ports requested (tcp/udp work, ranges also work)
 - sudo nft add's pre-routing rules to do your proxying for you

Examples
========
Given:

docker_compose.yml
```yaml
 ---
 version "2.1"
 networks:
   private_br:
    name: private_br
    driver: bridge
    ipam:
      driver: default
      config:
        - subnet: 192.168.2.0/24
    driver_opts:
      com.docker.network.bridge.name: docker_priv_br
      com.docker.network.bridge.enable_ip_masquerade: "true"

 services:
   nginx-proxy-manager:
     image: jc21/nginx-proxy-manager:latest
     ports:
       - '80:80'
       - '81:81'
       - '443:443'
     volumes:
      - ./npm:/data
    networks:
      private_br:
        ipv4_address: 192.168.2.5
 ...
```
Running this:
```
nft_tool.py --add --service nginx-proxy-manager --table global --chain preroute docker-compose.yml
```
Results in the following nft commands running:
```
sudo nft add rule ip global preroute fib daddr type local tcp dport 80 dnat to 192.168.2.5:80
sudo nft add rule ip global preroute fib daddr type local tcp dport 81 dnat to 192.168.2.5:81
sudo nft add rule ip global preroute fib daddr type local tcp dport 443 dnat to 192.168.2.5:443
```

So if I can translate the first rule there, it says:

Hey nftables, in the global table, the preroute chain, and forward local connections to port 80 on the docker-containers ip, port 80.


Running this:
```
nft_tool.py --delete --service nginx-proxy-manager --table global --chain preroute docker-compose.yml
```

Queries your nftable rules and matches with the "add" args:
```
 sudo nft -a list ruleset | grep 'fib daddr type local tcp dport 80 dnat to 192.168.2.5:80' | grep -o 'handle [0-9]*'
```
And feeds those handles back to nft delete commands:
```
sudo nft delete rule global preroute handle 69
```

TODO
====
I am not in love with needing to supply a specific IP for each container, I don't know a better way.

I'd like to add functionality to allow external access to requested services.
I think this would need to use a "label" on the service to indicate that it should be "external"
For now I open so few ports that it makes sense to just encode them in my static firewall rules, plus, how many do you need open when you have ngingx-proxy-manager, trafik\
, etc.

