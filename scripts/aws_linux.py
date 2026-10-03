#!/usr/bin/env python3
"""Linux CLI helpers for the AWS migration and disposable SOCKS5 tests."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
AMI_PARAMETER = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
TAGS = "ResourceType={kind},Tags=[{{Key=Name,Value={name}}},{{Key=Purpose,Value=ephemeral-test}}]"


def run(*args: str, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, input=input_text, text=True, capture_output=True, check=False)
    if check and result.returncode:
        raise RuntimeError(f"{' '.join(args[:3])} falhou: {result.stderr.strip() or result.stdout.strip()}")
    return result


def output(*args: str) -> str:
    return run(*args).stdout.strip()


def aws(state: dict, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("aws", *args, "--region", state["AwsRegion"], "--profile", state["AwsProfile"], check=check)


def aws_text(state: dict, *args: str, query: str) -> str:
    value = aws(state, *args, "--query", query, "--output", "text").stdout.strip()
    if not value or value == "None":
        raise RuntimeError(f"Resposta AWS vazia para {args[:2]} ({query})")
    return value


def save(state: dict, path: Path) -> None:
    state["UpdatedAt"] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    tmp.chmod(0o600)
    tmp.replace(path)


def tag(kind: str, name: str) -> str:
    return TAGS.format(kind=kind, name=name)


def ssh_options(state: dict) -> list[str]:
    # O IP literal da EC2 escolhe a família do transporte. -6 também limitaria
    # os destinos IPv4 do SOCKS5 reverso, como api.ipify.org.
    return ["-i", state["KeyFile"], "-o", "StrictHostKeyChecking=accept-new",
            "-o", f"UserKnownHostsFile={state['KnownHostsFile']}", "-o", "ConnectTimeout=15"]


def ssh(state: dict, command: str, *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("ssh", *ssh_options(state), f"ubuntu@{state['PublicIp']}", command, input_text=input_text, check=check)


def validate_endpoint(args: argparse.Namespace) -> None:
    state = {"AwsProfile": args.profile, "AwsRegion": args.region}
    service = f"com.amazonaws.{args.region}.cloudformation"
    result = aws(state, "ec2", "describe-vpc-endpoints", "--filters", f"Name=vpc-id,Values={args.vpc_id}",
                 f"Name=service-name,Values={service}", "--output", "json")
    endpoints = json.loads(result.stdout)["VpcEndpoints"]
    ready = [item for item in endpoints if item["State"] == "available" and item["PrivateDnsEnabled"]]
    if not ready:
        raise RuntimeError(f"A VPC {args.vpc_id} precisa de um endpoint CloudFormation disponível com Private DNS.")
    print(f"CloudFormation endpoint pronto: {ready[0]['VpcEndpointId']}")


def table(args: argparse.Namespace, delete: bool) -> None:
    state = {"AwsProfile": args.profile, "AwsRegion": args.region}
    if delete and not args.force:
        raise RuntimeError("Exclusão cancelada. Use --force para apagar permanentemente o histórico.")
    aws(state, "sts", "get-caller-identity")
    found = aws(state, "dynamodb", "describe-table", "--table-name", args.table,
                "--query", "Table.TableName", "--output", "text", check=False)
    if found.returncode and "ResourceNotFoundException" not in found.stderr:
        raise RuntimeError(found.stderr.strip())
    exists = found.returncode == 0
    if exists and found.stdout.strip() != args.table:
        raise RuntimeError("Resposta inesperada ao consultar a tabela DynamoDB.")
    if delete:
        if not exists:
            print(f"Tabela DynamoDB '{args.table}' não existe.")
            return
        aws(state, "dynamodb", "delete-table", "--table-name", args.table)
        aws(state, "dynamodb", "wait", "table-not-exists", "--table-name", args.table)
        print(f"Tabela DynamoDB '{args.table}' excluída permanentemente.")
        return
    tags = ["Key=Application,Value=loto-bot", "Key=Environment,Value=aws", "Key=ManagedBy,Value=script",
            "Key=Purpose,Value=bet-history"]
    if not exists:
        aws(state, "dynamodb", "create-table", "--table-name", args.table,
            "--attribute-definitions", "AttributeName=bet_id,AttributeType=S",
            "--key-schema", "AttributeName=bet_id,KeyType=HASH", "--billing-mode", "PAY_PER_REQUEST",
            "--tags", *tags)
    aws(state, "dynamodb", "wait", "table-exists", "--table-name", args.table)
    result = aws(state, "dynamodb", "describe-table", "--table-name", args.table, "--output", "json")
    info = json.loads(result.stdout)["Table"]
    hash_keys = [key["AttributeName"] for key in info["KeySchema"] if key["KeyType"] == "HASH"]
    billing = info.get("BillingModeSummary", {}).get("BillingMode", "PROVISIONED")
    if info["TableStatus"] != "ACTIVE" or hash_keys != ["bet_id"] or billing != "PAY_PER_REQUEST":
        raise RuntimeError(f"Tabela incompatível: status={info['TableStatus']}, chave={hash_keys}, billing={billing}")
    aws(state, "dynamodb", "tag-resource", "--resource-arn", info["TableArn"], "--tags", *tags)
    print(f"DynamoDB table: {args.table}\nStatus: ACTIVE\nBilling mode: {billing}\nRegion: {args.region}")


def start(args: argparse.Namespace) -> None:
    version = args.ip_version
    mode = "browser-socks5" if args.browser else "socks5"
    state_path = Path(args.state_file or SCRIPT_DIR / f"{mode}-ipv{version}-aws-state.json").resolve()
    if state_path.exists():
        raise RuntimeError(f"Estado já existe: {state_path}. Execute o script de limpeza ou use --state-file.")
    if args.browser and not Path(args.browser_test_script).is_file():
        raise RuntimeError(f"Teste do navegador não encontrado: {args.browser_test_script}")
    # No SOCKS5 remoto do ssh -R, o cliente SSH local resolve os destinos.
    for hostname in ("api.ipify.org", "www.loteriasonline.caixa.gov.br"):
        try:
            socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise RuntimeError(f"DNS local não resolveu {hostname}; corrija o resolvedor Linux antes de criar a EC2: {exc}") from exc
    public_ip = output("curl", "-6" if version == 6 else "-4", "-fsS", "https://api64.ipify.org" if version == 6 else "https://api.ipify.org")
    ipaddress.ip_address(public_ip)
    test_id = f"{mode}-ipv{version}-{int(time.time())}"
    state = {"TestId": test_id, "AwsProfile": args.profile, "AwsRegion": args.region,
             "InstanceType": args.instance_type, "IpVersion": version, "MyPublicIp": public_ip,
             "KeyFile": str(Path(tempfile.gettempdir()) / f"{test_id}.pem"),
             "KnownHostsFile": str(Path(tempfile.gettempdir()) / f"{test_id}-known-hosts"),
             "Status": "initializing"}
    save(state, state_path)

    def create(field: str, *command: str, query: str) -> str:
        value = aws_text(state, *command, query=query)
        state[field] = value
        save(state, state_path)
        return value

    try:
        aws(state, "sts", "get-caller-identity")
        vpc_args = ["ec2", "create-vpc", "--cidr-block", "10.77.0.0/16"]
        if version == 6:
            vpc_args.append("--amazon-provided-ipv6-cidr-block")
        vpc = create("VpcId", *vpc_args, "--tag-specifications", tag("vpc", test_id), query="Vpc.VpcId")
        aws(state, "ec2", "wait", "vpc-available", "--vpc-ids", vpc)
        ipv6_subnet = None
        if version == 6:
            for _ in range(30):
                block = aws(state, "ec2", "describe-vpcs", "--vpc-ids", vpc, "--query",
                            "Vpcs[0].Ipv6CidrBlockAssociationSet[?Ipv6CidrBlockState.State=='associated'].Ipv6CidrBlock | [0]",
                            "--output", "text").stdout.strip()
                if block and block != "None":
                    ipv6_subnet = str(next(ipaddress.ip_network(block).subnets(new_prefix=64)))
                    break
                time.sleep(2)
            if not ipv6_subnet:
                raise RuntimeError("A AWS não associou IPv6 à VPC.")
        gateway = create("InternetGatewayId", "ec2", "create-internet-gateway", "--tag-specifications",
                         tag("internet-gateway", test_id), query="InternetGateway.InternetGatewayId")
        aws(state, "ec2", "attach-internet-gateway", "--internet-gateway-id", gateway, "--vpc-id", vpc)
        zone = aws_text(state, "ec2", "describe-availability-zones", "--filters", "Name=state,Values=available",
                        query="AvailabilityZones[0].ZoneName")
        subnet_args = ["ec2", "create-subnet", "--vpc-id", vpc, "--cidr-block", "10.77.1.0/24",
                       "--availability-zone", zone]
        if ipv6_subnet:
            subnet_args += ["--ipv6-cidr-block", ipv6_subnet]
        subnet = create("SubnetId", *subnet_args, "--tag-specifications", tag("subnet", test_id), query="Subnet.SubnetId")
        if version == 6:
            aws(state, "ec2", "modify-subnet-attribute", "--subnet-id", subnet, "--assign-ipv6-address-on-creation")
        route = create("RouteTableId", "ec2", "create-route-table", "--vpc-id", vpc,
                       "--tag-specifications", tag("route-table", test_id), query="RouteTable.RouteTableId")
        destination = ["--destination-ipv6-cidr-block", "::/0"] if version == 6 else ["--destination-cidr-block", "0.0.0.0/0"]
        aws(state, "ec2", "create-route", "--route-table-id", route, *destination, "--gateway-id", gateway)
        create("RouteAssociationId", "ec2", "associate-route-table", "--route-table-id", route, "--subnet-id", subnet,
               query="AssociationId")
        group = create("SecurityGroupId", "ec2", "create-security-group", "--group-name", test_id,
                       "--description", "Temporary LotoBot SOCKS5 test", "--vpc-id", vpc,
                       "--tag-specifications", tag("security-group", test_id), query="GroupId")
        cidr = f"{public_ip}/{128 if version == 6 else 32}"
        if version == 6:
            aws(state, "ec2", "authorize-security-group-ingress", "--group-id", group, "--ip-permissions",
                f"IpProtocol=tcp,FromPort=22,ToPort=22,Ipv6Ranges=[{{CidrIpv6={cidr}}}]")
        else:
            aws(state, "ec2", "authorize-security-group-ingress", "--group-id", group, "--protocol", "tcp", "--port", "22", "--cidr", cidr)
        key = aws_text(state, "ec2", "create-key-pair", "--key-name", test_id, "--key-type", "ed25519",
                       "--key-format", "pem", "--tag-specifications", tag("key-pair", test_id), query="KeyMaterial")
        state["KeyPairCreated"] = True
        save(state, state_path)
        key_fd = os.open(state["KeyFile"], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(key_fd, "w") as key_file:
            key_file.write(key + "\n")
        ami = aws_text(state, "ssm", "get-parameter", "--name", AMI_PARAMETER, query="Parameter.Value")
        instance = create("InstanceId", "ec2", "run-instances", "--image-id", ami, "--instance-type", args.instance_type,
                          "--key-name", test_id, "--subnet-id", subnet, "--security-group-ids", group,
                          "--no-associate-public-ip-address" if version == 6 else "--associate-public-ip-address",
                          "--metadata-options", "HttpTokens=required,HttpEndpoint=enabled", "--credit-specification", "CpuCredits=standard",
                          "--block-device-mappings", "DeviceName=/dev/sda1,Ebs={VolumeSize=16,VolumeType=gp3,DeleteOnTermination=true,Encrypted=true}",
                          "--tag-specifications", tag("instance", test_id), query="Instances[0].InstanceId")
        aws(state, "ec2", "wait", "instance-status-ok", "--instance-ids", instance)
        ip_query = "Reservations[0].Instances[0].NetworkInterfaces[0].Ipv6Addresses[0].Ipv6Address" if version == 6 else "Reservations[0].Instances[0].PublicIpAddress"
        create("PublicIp", "ec2", "describe-instances", "--instance-ids", instance, query=ip_query)
        for attempt in range(30):
            if ssh(state, "true", check=False).returncode == 0:
                break
            print(f"Aguardando SSH ({attempt + 1}/30)...", flush=True)
            time.sleep(10)
        else:
            raise RuntimeError("A instância ficou saudável, mas o SSH não respondeu.")
        if args.browser:
            provision = """set -eu
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv xvfb xauth
python3 -m venv /tmp/lotobot-browser-proxy-venv
/tmp/lotobot-browser-proxy-venv/bin/pip install --quiet playwright
sudo /tmp/lotobot-browser-proxy-venv/bin/python -m playwright install-deps chromium
/tmp/lotobot-browser-proxy-venv/bin/python -m playwright install chromium
"""
            ssh(state, "bash -s", input_text=provision)
            destination = f"ubuntu@[{state['PublicIp']}]:/tmp/test_browser_proxy.py" if version == 6 else f"ubuntu@{state['PublicIp']}:/tmp/test_browser_proxy.py"
            run("scp", *ssh_options(state), args.browser_test_script, destination)
        else:
            ssh(state, "sudo apt-get update -qq && sudo apt-get install -y -qq curl")
        tunnel = subprocess.Popen(["ssh", *ssh_options(state), "-N", "-T", "-o", "ExitOnForwardFailure=yes",
                                   "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
                                   "-R", "127.0.0.1:1080", f"ubuntu@{state['PublicIp']}"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
        state["TunnelProcessId"] = tunnel.pid
        save(state, state_path)
        time.sleep(5)
        if tunnel.poll() is not None:
            raise RuntimeError(f"Túnel SSH terminou: {tunnel.stderr.read().decode().strip()}")
        if args.browser:
            command = "ss -lnt | grep -q '127.0.0.1:1080' && xvfb-run -a env BROWSER_PROXY_SERVER=socks5://127.0.0.1:1080 /tmp/lotobot-browser-proxy-venv/bin/python /tmp/test_browser_proxy.py"
            result = ssh(state, command)
            print(result.stdout)
            if "Teste CAIXA via Chromium: OK" not in result.stdout:
                raise RuntimeError("O Chromium não confirmou a página da CAIXA.")
        else:
            command = "set -eu; ss -lnt | grep -q '127.0.0.1:1080'; echo \"IP direto da EC2: $(curl -fsS --max-time 20 https://api.ipify.org)\"; echo \"IP pelo SOCKS5: $(curl -fsS --max-time 20 --socks5-hostname 127.0.0.1:1080 https://api.ipify.org)\"; curl -fsSL --max-time 20 --socks5-hostname 127.0.0.1:1080 -o /dev/null https://www.loteriasonline.caixa.gov.br/silce-web/#/termos-de-uso"
            result = ssh(state, command)
            print(result.stdout)
            proxy_line = next((line for line in result.stdout.splitlines() if line.startswith("IP pelo SOCKS5: ")), "")
            if proxy_line.removeprefix("IP pelo SOCKS5: ") != public_ip:
                raise RuntimeError("O IP do SOCKS5 difere da saída local.")
        os.killpg(tunnel.pid, signal.SIGTERM)
        tunnel.wait(timeout=10)
        state.pop("TunnelProcessId", None)
        save(state, state_path)
        if args.browser:
            fail_command = "timeout 45s xvfb-run -a env BROWSER_PROXY_SERVER=socks5://127.0.0.1:1080 /tmp/lotobot-browser-proxy-venv/bin/python /tmp/test_browser_proxy.py --expect-proxy-failure"
        else:
            fail_command = "! curl -fsS --max-time 5 --socks5-hostname 127.0.0.1:1080 https://api.ipify.org"
        if ssh(state, fail_command, check=False).returncode:
            raise RuntimeError("O teste fail-closed falhou após encerrar o túnel.")
        state["Status"] = "ready-for-cleanup"
        save(state, state_path)
        print(f"Teste aprovado. Recursos ativos; limpe com scripts/stop-socks5-ipv{version}-aws.sh --state-file {state_path}")
    except Exception:
        state["Status"] = "initialization-failed"
        save(state, state_path)
        raise


def stop(args: argparse.Namespace) -> None:
    plain_state = SCRIPT_DIR / f"socks5-ipv{args.ip_version}-aws-state.json"
    browser_state = SCRIPT_DIR / f"browser-socks5-ipv{args.ip_version}-aws-state.json"
    default_state = browser_state if args.browser or (browser_state.exists() and not plain_state.exists()) else plain_state
    path = Path(args.state_file or default_state).resolve()
    state = json.loads(path.read_text())
    if args.profile:
        state["AwsProfile"] = args.profile
    if args.region:
        state["AwsRegion"] = args.region
    if state.get("IpVersion") != args.ip_version:
        raise RuntimeError("Versão IP do estado não corresponde ao script de limpeza.")
    failures = []

    def attempt(label: str, *command: str) -> bool:
        result = aws(state, *command, check=False)
        if result.returncode:
            if "NotFound" in result.stderr or "does not exist" in result.stderr:
                return True
            failures.append(f"{label}: {result.stderr.strip()}")
            return False
        return True

    pid = state.get("TunnelProcessId")
    if pid:
        try:
            command = Path(f"/proc/{pid}/cmdline").read_bytes()
            if b"ssh\0" in command and b"127.0.0.1:1080" in command:
                os.killpg(pid, signal.SIGTERM)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    if state.get("InstanceId"):
        if attempt("terminate instance", "ec2", "terminate-instances", "--instance-ids", state["InstanceId"]):
            attempt("wait instance", "ec2", "wait", "instance-terminated", "--instance-ids", state["InstanceId"])
    if state.get("SecurityGroupId"):
        attempt("delete security group", "ec2", "delete-security-group", "--group-id", state["SecurityGroupId"])
    if state.get("RouteAssociationId"):
        attempt("disassociate route", "ec2", "disassociate-route-table", "--association-id", state["RouteAssociationId"])
    if state.get("RouteTableId"):
        attempt("delete route table", "ec2", "delete-route-table", "--route-table-id", state["RouteTableId"])
    if state.get("SubnetId"):
        attempt("delete subnet", "ec2", "delete-subnet", "--subnet-id", state["SubnetId"])
    if state.get("InternetGatewayId") and state.get("VpcId"):
        if attempt("detach gateway", "ec2", "detach-internet-gateway", "--internet-gateway-id", state["InternetGatewayId"], "--vpc-id", state["VpcId"]):
            attempt("delete gateway", "ec2", "delete-internet-gateway", "--internet-gateway-id", state["InternetGatewayId"])
    if state.get("VpcId"):
        attempt("delete VPC", "ec2", "delete-vpc", "--vpc-id", state["VpcId"])
    if state.get("KeyPairCreated"):
        attempt("delete key pair", "ec2", "delete-key-pair", "--key-name", state["TestId"])
    for kind, query in [("instances", "Reservations[].Instances[].{Id:InstanceId,State:State.Name}"), ("vpcs", "Vpcs[].VpcId")]:
        attempt(f"audit {kind}", "ec2", f"describe-{kind}", "--filters", f"Name=tag:Name,Values={state['TestId']}", "--query", query, "--output", "table")
    if failures:
        raise RuntimeError("Limpeza com pendências; estado preservado em " + str(path) + "\n" + "\n".join(failures))
    for field in ("KeyFile", "KnownHostsFile"):
        file = Path(state[field])
        if file.parent == Path(tempfile.gettempdir()) and file.name.startswith(state["TestId"]):
            file.unlink(missing_ok=True)
    path.unlink()
    print("Limpeza concluída; estado local removido.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("create-table", "delete-table", "endpoint", "start", "stop"):
        item = sub.add_parser(name)
        item.add_argument("--profile", required=name != "stop")
        item.add_argument("--region", required=name != "stop")
        if name in ("create-table", "delete-table"):
            item.add_argument("--table", default="loto-bot-bets")
            if name == "delete-table":
                item.add_argument("--force", action="store_true")
        elif name == "endpoint":
            item.add_argument("--vpc-id", required=True)
        else:
            item.add_argument("--ip-version", type=int, choices=(4, 6), required=True)
            item.add_argument("--browser", action="store_true")
            item.add_argument("--state-file")
            if name == "start":
                item.add_argument("--instance-type", default="t3.micro")
                item.add_argument("--browser-test-script", default=str(SCRIPT_DIR / "test_browser_proxy.py"))
    args = parser.parse_args()
    try:
        if args.command == "create-table":
            table(args, False)
        elif args.command == "delete-table":
            table(args, True)
        elif args.command == "endpoint":
            validate_endpoint(args)
        elif args.command == "start":
            start(args)
        else:
            stop(args)
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
