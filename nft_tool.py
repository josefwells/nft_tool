#!/usr/bin/env python3
"""
This script reads a docker-compose.yaml file and generates nftables command lines for each service.
"""

import argparse
import logging
import subprocess

import yaml


def run_cmd(command, message, dryrun):
    """
    Run a command, or don't what do I care
    """
    if dryrun:
        logging.info("DRYRUN: %s", command)
        return
    logging.info("RUNNING: %s", command)
    try:
        subprocess.run(command, check=True, shell=True)
    except subprocess.CalledProcessError:
        logging.error("%s", message)


def port_loop(args, network_name, service_yaml):
    """
    Pass each set of ports down for processing

    :param args: Arguments passed through
    :param network_name: The name of the docker_compose network
    :param service_yaml: A dictionary containing the service data
    """
    # Get the IP address for the service
    ipv4_address = service_yaml["networks"][network_name]["ipv4_address"]

    # Loop through each port mapping for the service
    for ports in service_yaml.get("ports", []):
        nft_rules_for_ports(ports, ipv4_address, args)


def parse_ports(ports):
    """
    Parse each port specification.
    Handle hostport:containerport
    Handle ranges "-" delimited
    Handle trailing "/protocol" for tcp/udp
    TODO: Handle binding IP for automatic exposure to world
    TODO: Handle missing : when hostport==containerport
    """
    # Check for tcp/udp
    if "/" in ports:
        hostcont, proto = ports.split("/", 1)
    else:
        hostcont = ports
        proto = "tcp"

    # Split the port mapping into host and container ports
    if ":" in hostcont:
        host_port, container_port = hostcont.split(":")
    else:
        host_port = hostcont
        container_port = hostcont

    return (host_port, container_port, proto)


def nft_rules_for_ports(ports, ipv4_address, args):
    """
    Add/Delete nftables command lines for a port specification
    """
    (host_port, container_port, proto) = parse_ports(ports)

    # Generate the nftables command line
    add_pre = f"sudo nft add rule ip {args.table} {args.chain} "
    nft_rule = f"{proto} dport {host_port} dnat to {ipv4_address}:{container_port}"

    if args.add:
        run_cmd(
            add_pre + nft_rule,
            f"NFT rule add failed for {add_pre+nft_rule}",
            args.dryrun,
        )
    elif args.delete:
        list_cmd = (
            f"sudo nft -a list ruleset | grep '{nft_rule}' | grep -o 'handle [0-9]*'"
        )
        handle = False
        logging.info("RUNNING: %s", list_cmd)
        try:
            handle = subprocess.check_output(list_cmd, shell=True).strip().decode()
        except subprocess.CalledProcessError:
            logging.warning("Nft rule not found for service %s", args.service)
        if handle:
            del_cmd = f"sudo nft delete rule {args.table} {args.chain} {handle}"
            run_cmd(del_cmd, f"Nft rule delete failed for {del_cmd}", args.dryrun)

    else:
        logging.error("Must specify --add or --delete")


def main():
    """
    Main function that parses command-line arguments and generates nftables command lines.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Generate nftables command lines for Docker services"
    )
    parser.add_argument(
        "file", metavar="FILE", help="Path to the docker-compose.yaml file"
    )
    parser.add_argument(
        "--debug", metavar="DEBUG_LEVEL", default="WARN", help="Set logging level"
    )
    parser.add_argument(
        "--table", metavar="TABLE", default="nat", help="Name of the nft table"
    )
    parser.add_argument(
        "--chain", metavar="CHAIN", default="prerouting", help="Name of the nft chain"
    )
    parser.add_argument(
        "--service",
        metavar="SERVICE",
        help="Generate nftables rule for a specific service",
    )
    parser.add_argument(
        "--dryrun",
        "-n",
        action="store_true",
        default=False,
        help="Dry run, do not execute add/delete commands",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--add", action="store_true", default=False, help="Add new rule")
    group.add_argument(
        "--delete", action="store_true", default=False, help="Delete existing rule"
    )

    args = parser.parse_args()

    logging.basicConfig(level=args.debug)

    # Read the docker-compose.yaml file
    with open(args.file, "r", encoding="utf-8") as dc_file:
        dc_yaml = yaml.safe_load(dc_file)

    network_name = list(dc_yaml["networks"].keys())[0]

    # Loop through specified services port listings
    port_loop(args, network_name, dc_yaml["services"][args.service])


if __name__ == "__main__":
    main()
