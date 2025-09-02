#!/usr/bin/env python3

"""
EC2 Instance Management Script

Lists EC2 instances with their name, ID, IP address, and status.
Requires boto3 and AWS credentials configured.
"""

import boto3
import sys
import fnmatch
import json
import os
import time
import hashlib
import subprocess
from botocore.exceptions import ClientError, NoCredentialsError


def check_aws_credentials(region_override=None):
    """Check if AWS credentials are properly configured.
    
    Args:
        region_override: Region provided via command line argument
    
    Returns:
        True if credentials are configured, False otherwise
    """
    session = boto3.Session()
    credentials = session.get_credentials()
    
    if not credentials:
        print("Error: AWS credentials not found.")
        print("Please configure your AWS credentials:")
        print("  aws configure")
        print("\nRequired:")
        print("  - AWS Access Key ID")
        print("  - AWS Secret Access Key")
        print("  - Default region (e.g., us-east-1)")
        return False
    
    # Check if we have access key and secret key
    if not credentials.access_key or not credentials.secret_key:
        print("Error: Incomplete AWS credentials.")
        print("Please ensure you have set:")
        print("  - AWS Access Key ID")
        print("  - AWS Secret Access Key")
        print("\nRun: aws configure")
        return False
    
    # Check if region is configured (skip if region provided via argument)
    if not region_override and not session.region_name:
        print("Error: AWS region not configured.")
        print("Please set a default region:")
        print("  aws configure set region us-east-1")
        print("Or use: --region us-east-1")
        return False
    
    return True


def get_ec2_client(region=None, access_key=None, secret_key=None):
    """Create and return an EC2 client.

    Args:
        region: AWS region (uses default if not specified)
        access_key: AWS Access Key ID (uses default if not specified)
        secret_key: AWS Secret Access Key (uses default if not specified)

    Returns:
        boto3 EC2 client
    """
    try:
        client_kwargs = {}
        
        if region:
            client_kwargs['region_name'] = region
        
        if access_key and secret_key:
            client_kwargs['aws_access_key_id'] = access_key
            client_kwargs['aws_secret_access_key'] = secret_key
        
        return boto3.client('ec2', **client_kwargs)
        
    except NoCredentialsError:
        print("Error: AWS credentials not found. "
              "Please configure your credentials.")
        print("Run: aws configure")
        sys.exit(1)


def get_cache_filename(region, access_key=None, secret_key=None):
    """Generate cache filename based on region and credentials.
    
    Args:
        region: AWS region
        access_key: AWS Access Key ID (optional)
        secret_key: AWS Secret Access Key (optional)
    
    Returns:
        Cache filename path
    """
    # Use default region if not specified
    if not region:
        session = boto3.Session()
        region = session.region_name
        if not region:
            # Try to get from EC2 client metadata
            try:
                ec2 = boto3.client('ec2')
                region = ec2.meta.region_name
            except:
                region = 'default'
    
    # Create hash of credentials for uniqueness
    if access_key and secret_key:
        cred_hash = hashlib.md5(
            f"{access_key}{secret_key}".encode()
        ).hexdigest()[:8]
    else:
        # Use default credentials identifier
        session = boto3.Session()
        creds = session.get_credentials()
        if creds:
            cred_hash = hashlib.md5(
                f"{creds.access_key}{creds.secret_key}".encode()
            ).hexdigest()[:8]
        else:
            cred_hash = 'nocreds'
    
    # Include region in filename to ensure separate caches per region
    safe_region = region.replace('-', '_')
    return f"/tmp/ec2_cache_{safe_region}_{cred_hash}.json"


def is_cache_valid(cache_file, ttl=300):
    """Check if cache file is valid (exists and not expired).
    
    Args:
        cache_file: Path to cache file
        ttl: Time to live in seconds (default 5 minutes)
    
    Returns:
        True if cache is valid, False otherwise
    """
    if not os.path.exists(cache_file):
        return False
    
    # Check file age
    file_age = time.time() - os.path.getmtime(cache_file)
    return file_age < ttl


def load_cache(cache_file):
    """Load instances from cache file.
    
    Args:
        cache_file: Path to cache file
    
    Returns:
        List of instances or None if error
    """
    try:
        with open(cache_file, 'r') as f:
            data = json.load(f)
            return data.get('instances', [])
    except (IOError, json.JSONDecodeError):
        return None


def save_cache(cache_file, instances, region):
    """Save instances to cache file.
    
    Args:
        cache_file: Path to cache file
        instances: List of instances to cache
        region: AWS region
    """
    try:
        data = {
            'timestamp': time.time(),
            'region': region,
            'instances': instances
        }
        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)
    except IOError:
        # Silently fail if can't write cache
        pass


def get_instance_name(instance):
    """Extract instance name from tags.

    Args:
        instance: EC2 instance dictionary

    Returns:
        Instance name or 'N/A' if no name tag exists
    """
    if 'Tags' in instance:
        for tag in instance['Tags']:
            if tag['Key'] == 'Name':
                return tag['Value']
    return 'N/A'


def list_ec2_instances(region=None, access_key=None, secret_key=None,
                       use_cache=True):
    """List all EC2 instances in the specified region.

    Args:
        region: AWS region to query
        access_key: AWS Access Key ID (optional)
        secret_key: AWS Secret Access Key (optional)
        use_cache: Whether to use cached results (default True)

    Returns:
        List of dictionaries containing instance information
    """
    # Check cache first
    cache_file = get_cache_filename(region, access_key, secret_key)
    
    if use_cache and is_cache_valid(cache_file):
        cached_instances = load_cache(cache_file)
        if cached_instances is not None:
            print(f"Using cached data (from {cache_file})")
            return cached_instances
    
    # No valid cache, fetch from AWS
    ec2 = get_ec2_client(region, access_key, secret_key)
    
    try:
        response = ec2.describe_instances()
        instances = []
        
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_info = {
                    'name': get_instance_name(instance),
                    'id': instance['InstanceId'],
                    'status': instance['State']['Name'],
                    'type': instance['InstanceType'],
                    'public_ip': instance.get('PublicIpAddress', 'N/A'),
                    'private_ip': instance.get('PrivateIpAddress', 'N/A'),
                    'region': region or ec2.meta.region_name
                }
                instances.append(instance_info)
        
        # Save to cache
        if use_cache:
            save_cache(cache_file, instances, region or ec2.meta.region_name)
            print(f"Cached data saved to {cache_file}")
        
        return instances
        
    except ClientError as e:
        print(f"Error: {e}")
        sys.exit(1)


def filter_instances_by_name(instances, name_pattern):
    """Filter instances by name pattern with wildcard support.

    Args:
        instances: List of instance dictionaries
        name_pattern: Pattern to match (supports * and ? wildcards)

    Returns:
        Filtered list of instances
    """
    if not name_pattern:
        return instances
    
    # Add wildcards if not present
    if '*' not in name_pattern and '?' not in name_pattern:
        name_pattern = f"*{name_pattern}*"
    
    filtered_instances = []
    for instance in instances:
        instance_name = instance.get('name', 'N/A').lower()
        if fnmatch.fnmatch(instance_name, name_pattern.lower()):
            filtered_instances.append(instance)
    
    return filtered_instances


def find_instance_by_name(name_pattern, region=None, access_key=None,
                         secret_key=None):
    """Find instance(s) by name pattern.
    
    Args:
        name_pattern: Name or partial name of instance
        region: AWS region
        access_key: AWS Access Key ID (optional)
        secret_key: AWS Secret Access Key (optional)
    
    Returns:
        List of matching instances
    """
    # Get all instances (use cache if available)
    instances = list_ec2_instances(region, access_key, secret_key)
    
    # First try exact match
    exact_matches = [i for i in instances 
                     if i['name'].lower() == name_pattern.lower()]
    if exact_matches:
        return exact_matches
    
    # Then try partial match
    partial_matches = [i for i in instances 
                      if name_pattern.lower() in i['name'].lower()]
    
    return partial_matches


def is_tmux_session():
    """Check if running inside tmux session.
    
    Returns:
        True if inside tmux, False otherwise
    """
    return os.environ.get('TMUX') is not None


def get_ssh_credentials():
    """Get SSH credentials from environment variables.
    
    Returns:
        List of (username, key_file) tuples to try
    """
    env_users = os.environ.get('EC2_USERNAME', '').strip()
    env_keys = os.environ.get('EC2_SSHKEY', '').strip()
    
    if not env_users:
        return []
    
    # Parse usernames and keys
    usernames = [u.strip() for u in env_users.split(',') if u.strip()]
    keyfiles = [k.strip() for k in env_keys.split(',') if k.strip()] if env_keys else [None]
    
    # Create all combinations: first user with all keys, then second user with all keys, etc.
    combinations = []
    for username in usernames:
        for keyfile in keyfiles:
            combinations.append((username, keyfile))
    
    return combinations


def guess_ssh_user(instance):
    """Guess SSH user based on instance name.
    
    Args:
        instance: Instance dictionary
    
    Returns:
        Guessed username
    """
    instance_name = instance['name'].lower()
    if 'ubuntu' in instance_name:
        return 'ubuntu'
    elif 'centos' in instance_name:
        return 'centos'
    elif 'debian' in instance_name:
        return 'admin'
    else:
        return 'ec2-user'  # Amazon Linux default


def ssh_to_instance(instance, user=None, key_file=None, port=22,
                    ssh_opts="", use_tmux=None):
    """SSH to an EC2 instance.
    
    Args:
        instance: Instance dictionary
        user: SSH user (optional, will use env vars or guess)
        key_file: Path to SSH key file (optional, will use env vars)
        port: SSH port (default 22)
        ssh_opts: Additional SSH options
        use_tmux: Force tmux usage (None=auto, True=force, False=disable)
    """
    # Prefer public IP, fallback to private
    ip = instance['public_ip']
    if ip == 'N/A':
        ip = instance['private_ip']
        if ip == 'N/A':
            print(f"Error: No IP address found for {instance['name']}")
            return False
    
    # Get credentials to try
    ssh_attempts = []
    
    if user and key_file:
        # User provided both user and key via command line
        ssh_attempts.append((user, key_file))
    elif user:
        # User provided username only
        ssh_attempts.append((user, key_file))
    else:
        # Try environment variables first
        env_credentials = get_ssh_credentials()
        ssh_attempts.extend(env_credentials)
        
        # If no env vars, fall back to guessing
        if not env_credentials:
            guessed_user = guess_ssh_user(instance)
            ssh_attempts.append((guessed_user, key_file))
    
    # Try each credential combination
    for attempt_user, attempt_key in ssh_attempts:
        # Build SSH command
        ssh_cmd = ['ssh']
        
        # Add verbose flag if EC2_SSH_VERBOSE is set
        if os.environ.get('EC2_SSH_VERBOSE', '').lower() in ('1', 'true', 'yes', 'on'):
            ssh_cmd.append('-v')
        
        # Add connection timeout and other useful options
        ssh_cmd.extend(['-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=no'])
        
        if attempt_key and os.path.exists(attempt_key):
            ssh_cmd.extend(['-i', attempt_key])
        elif attempt_key:
            print(f"Warning: SSH key not found: {attempt_key}")
            continue
        
        if port != 22:
            ssh_cmd.extend(['-p', str(port)])
        
        if ssh_opts:
            ssh_cmd.extend(ssh_opts.split())
        
        ssh_cmd.append(f"{attempt_user}@{ip}")
        
        # Show what we're trying
        key_info = f" with key {attempt_key}" if attempt_key else ""
        verbose_info = " (verbose)" if os.environ.get('EC2_SSH_VERBOSE') else ""
        print(f"Trying {attempt_user}@{ip}{key_info}{verbose_info}...")
        
        # Determine if we should use tmux
        should_use_tmux = use_tmux if use_tmux is not None else is_tmux_session()
        
        if should_use_tmux:
            # Create new tmux window that stays open after SSH session ends
            window_name = instance['name'][:20]  # Limit window name length
            # Use tmux new-window with shell command that keeps window open
            escaped_cmd = ' '.join(f"'{arg}'" for arg in ssh_cmd)
            tmux_cmd = f"tmux new-window -n '{window_name}' \"bash -c '{escaped_cmd}; echo; echo SSH session ended. Press Enter to close window.; read'\""
            print(f"Opening SSH to {instance['name']} ({ip}) in new tmux window...")
            subprocess.run(tmux_cmd, shell=True)
            return True
        else:
            # Direct SSH - try this combination
            print(f"Connecting to {instance['name']} ({ip})...")
            result = subprocess.run(ssh_cmd)
            
            # If SSH was successful (exit code 0), we're done
            if result.returncode == 0:
                return True
            
            # If we have more attempts, continue trying
            if ssh_attempts.index((attempt_user, attempt_key)) < len(ssh_attempts) - 1:
                print(f"Connection failed with {attempt_user}, trying next credential...")
                continue
    
    # All attempts failed
    print(f"Error: Could not connect to {instance['name']} with any available credentials")
    return False


def show_configuration():
    """Show AWS configuration and environment variables."""
    print("=" * 50)
    print("EC2 Configuration")
    print("=" * 50)
    
    # AWS Configuration
    print("\nAWS Configuration:")
    print("-" * 20)
    
    session = boto3.Session()
    credentials = session.get_credentials()
    
    if credentials:
        # Mask sensitive information
        access_key = credentials.access_key
        if access_key:
            masked_key = access_key[:4] + "*" * (len(access_key) - 8) + access_key[-4:]
            print(f"Access Key ID:     {masked_key}")
        else:
            print("Access Key ID:     Not configured")
        
        secret_key = credentials.secret_key
        if secret_key:
            print(f"Secret Access Key: {'*' * len(secret_key[:4])}***{'*' * len(secret_key[-4:])}")
        else:
            print("Secret Access Key: Not configured")
    else:
        print("Access Key ID:     Not configured")
        print("Secret Access Key: Not configured")
    
    # Region
    region = session.region_name
    if region:
        print(f"Default Region:    {region}")
    else:
        try:
            ec2 = boto3.client('ec2')
            region = ec2.meta.region_name
            if region:
                print(f"Default Region:    {region} (from client)")
            else:
                print("Default Region:    Not configured")
        except:
            print("Default Region:    Not configured")
    
    # Profile
    profile = session.profile_name
    if profile and profile != 'default':
        print(f"Profile:           {profile}")
    else:
        print("Profile:           default")
    
    # Environment Variables
    print("\nEnvironment Variables:")
    print("-" * 22)
    
    ec2_username = os.environ.get('EC2_USERNAME', '')
    ec2_sshkey = os.environ.get('EC2_SSHKEY', '')
    ec2_ssh_verbose = os.environ.get('EC2_SSH_VERBOSE', '')
    
    if ec2_username:
        usernames = [u.strip() for u in ec2_username.split(',') if u.strip()]
        print(f"EC2_USERNAME:      {', '.join(usernames)}")
    else:
        print("EC2_USERNAME:      Not set")
    
    if ec2_sshkey:
        keyfiles = [k.strip() for k in ec2_sshkey.split(',') if k.strip()]
        print("EC2_SSHKEY:")
        for i, keyfile in enumerate(keyfiles, 1):
            # Check if key file exists
            expanded_path = os.path.expanduser(keyfile)
            exists = os.path.exists(expanded_path)
            status = "✓" if exists else "✗"
            print(f"  {i}. {keyfile} {status}")
    else:
        print("EC2_SSHKEY:        Not set")
    
    if ec2_ssh_verbose:
        verbose_enabled = ec2_ssh_verbose.lower() in ('1', 'true', 'yes', 'on')
        status = "Enabled" if verbose_enabled else f"Set but disabled ({ec2_ssh_verbose})"
        print(f"EC2_SSH_VERBOSE:   {status}")
    else:
        print("EC2_SSH_VERBOSE:   Not set")
    
    # SSH Credential Combinations
    print("\nSSH Credential Combinations:")
    print("-" * 28)
    
    env_credentials = get_ssh_credentials()
    if env_credentials:
        print("Will try these combinations in order:")
        for i, (username, keyfile) in enumerate(env_credentials, 1):
            key_display = keyfile if keyfile else "(no key file)"
            print(f"  {i}. {username} + {key_display}")
    else:
        print("No environment credentials configured.")
        print("Will use auto-detection based on instance names:")
        print("  - ubuntu    (for instances with 'ubuntu' in name)")
        print("  - centos    (for instances with 'centos' in name)")  
        print("  - admin     (for instances with 'debian' in name)")
        print("  - ec2-user  (default for other instances)")
    
    # AWS CLI Configuration Files
    print("\nAWS CLI Configuration:")
    print("-" * 22)
    
    aws_config_dir = os.path.expanduser('~/.aws')
    config_file = os.path.join(aws_config_dir, 'config')
    credentials_file = os.path.join(aws_config_dir, 'credentials')
    
    if os.path.exists(config_file):
        print(f"Config file:       {config_file} ✓")
    else:
        print(f"Config file:       {config_file} ✗")
    
    if os.path.exists(credentials_file):
        print(f"Credentials file:  {credentials_file} ✓")
    else:
        print(f"Credentials file:  {credentials_file} ✗")
    
    print("\n" + "=" * 50)


def print_instances_table(instances):
    """Print instances in a formatted table.

    Args:
        instances: List of instance dictionaries
    """
    if not instances:
        print("No EC2 instances found.")
        return
    
    # Color codes
    GREEN = '\033[92m'
    RED = '\033[91m'
    GRAY = '\033[90m'
    RESET = '\033[0m'
    
    # Calculate column widths
    name_width = max(len(inst['name']) for inst in instances)
    name_width = max(name_width, 4)  # Minimum width for "NAME"
    
    id_width = max(len(inst['id']) for inst in instances)
    id_width = max(id_width, 10)  # Minimum width for "INSTANCE ID"
    
    status_width = max(len(inst['status']) for inst in instances)
    status_width = max(status_width, 6)  # Minimum width for "STATUS"
    
    type_width = max(len(inst['type']) for inst in instances)
    type_width = max(type_width, 4)  # Minimum width for "TYPE"
    
    # Print header
    header = (f"{'NAME':<{name_width}} {'INSTANCE ID':<{id_width}} "
              f"{'STATUS':<{status_width}} {'TYPE':<{type_width}} "
              f"{'PUBLIC IP':<15} {'PRIVATE IP':<15}")
    print(header)
    print("-" * (name_width + id_width + status_width + type_width + 35))
    
    # Print instances
    for instance in instances:
        # Color the status
        status = instance['status']
        if status == 'running':
            colored_status = f"{GREEN}{status}{RESET}"
        elif status == 'stopped':
            colored_status = f"{RED}{status}{RESET}"
        elif status == 'terminated':
            colored_status = f"{GRAY}{status}{RESET}"
        else:
            colored_status = status
        
        # Adjust padding for colored status (ANSI codes don't count in width)
        status_padding = status_width - len(status)
        
        row = (f"{instance['name']:<{name_width}} "
               f"{instance['id']:<{id_width}} "
               f"{colored_status}{' ' * status_padding} "
               f"{instance['type']:<{type_width}} "
               f"{instance['public_ip']:<15} "
               f"{instance['private_ip']:<15}")
        print(row)


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='EC2 management tool',
                                     usage='%(prog)s {list,ssh,showconfig} [options]')
    
    # Positional arguments
    parser.add_argument('command', choices=['list', 'ssh', 'showconfig'],
                        help='Command to execute')
    parser.add_argument('name_pattern', nargs='?',
                        help='For list: filter pattern, For ssh: instance name')
    
    # Optional arguments
    parser.add_argument('-r', '--region',
                        help='AWS region (e.g., us-east-1)')
    parser.add_argument('-a', '--all-regions', action='store_true',
                        help='List instances from all regions')
    parser.add_argument('--access-key',
                        help='AWS Access Key ID (overrides config)')
    parser.add_argument('--secret-key',
                        help='AWS Secret Access Key (overrides config)')
    parser.add_argument('--no-cache', action='store_true',
                        help='Force refresh, ignore cached data')
    
    # SSH specific options
    parser.add_argument('--user', '-u',
                        help='SSH user (default: auto-detect)')
    parser.add_argument('--key', '-i',
                        help='Path to SSH private key')
    parser.add_argument('--port', '-p', type=int, default=22,
                        help='SSH port (default: 22)')
    parser.add_argument('--format',
                        help='Output format (names: for autocomplete)')
    parser.add_argument('--tmux', action='store_true',
                        help='Force open in tmux window')
    parser.add_argument('--no-tmux', action='store_true',
                        help='Disable tmux integration')
    
    args = parser.parse_args()
    
    # Check credentials if not provided via arguments (skip for showconfig)
    if args.command != 'showconfig':
        if not args.access_key or not args.secret_key:
            if not check_aws_credentials(args.region):
                sys.exit(1)
    
    # Handle list command
    if args.command == 'list':
        # Determine if we should use cache
        use_cache = not args.no_cache
        
        if args.all_regions:
            # Get list of all regions
            ec2 = get_ec2_client(None, args.access_key, args.secret_key)
            try:
                regions_response = ec2.describe_regions()
                regions = [region['RegionName']
                           for region in regions_response['Regions']]
                
                all_instances = []
                for region in regions:
                    print(f"Checking region: {region}")
                    instances = list_ec2_instances(region, args.access_key,
                                                   args.secret_key, use_cache)
                    all_instances.extend(instances)
                
                # Filter instances by name pattern
                filtered_instances = filter_instances_by_name(all_instances,
                                                              args.name_pattern)
                
                print(f"\nTotal instances found: {len(all_instances)}")
                if args.name_pattern:
                    print(f"Filtered by '{args.name_pattern}': "
                          f"{len(filtered_instances)} instances")
                
                # Check for special format output
                if args.format == 'names':
                    # Output only instance names for autocomplete
                    for inst in filtered_instances:
                        print(inst['name'])
                else:
                    print_instances_table(filtered_instances)
                
            except ClientError as e:
                print(f"Error getting regions: {e}")
                sys.exit(1)
        else:
            # Single region
            instances = list_ec2_instances(args.region, args.access_key,
                                           args.secret_key, use_cache)
            
            # Filter instances by name pattern
            filtered_instances = filter_instances_by_name(instances,
                                                          args.name_pattern)
            
            if args.name_pattern:
                print(f"Filtered by '{args.name_pattern}': "
                      f"{len(filtered_instances)} of {len(instances)} instances")
            
            # Check for special format output
            if args.format == 'names':
                # Output only instance names for autocomplete
                for inst in filtered_instances:
                    print(inst['name'])
            else:
                print_instances_table(filtered_instances)
    
    elif args.command == 'ssh':
        # SSH command requires instance name
        if not args.name_pattern:
            print("Error: Instance name required for ssh command")
            print("Usage: ec2.py ssh <instance-name>")
            sys.exit(1)
        
        # Find matching instances
        matches = find_instance_by_name(args.name_pattern, args.region,
                                       args.access_key, args.secret_key)
        
        if not matches:
            print(f"Error: No instance found matching '{args.name_pattern}'")
            sys.exit(1)
        
        if len(matches) > 1:
            print(f"Error: Multiple instances match '{args.name_pattern}':")
            for inst in matches:
                print(f"  - {inst['name']} ({inst['id']}) - {inst['status']}")
            print("\nPlease be more specific.")
            sys.exit(1)
        
        # Single match found
        instance = matches[0]
        
        # Check if instance is running
        if instance['status'] != 'running':
            print(f"Warning: Instance {instance['name']} is {instance['status']}")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                sys.exit(0)
        
        # Determine tmux usage
        use_tmux = None
        if args.tmux:
            use_tmux = True
        elif args.no_tmux:
            use_tmux = False
        
        # SSH to the instance
        ssh_to_instance(instance, user=args.user, key_file=args.key,
                       port=args.port, use_tmux=use_tmux)
    
    elif args.command == 'showconfig':
        # Show configuration - no credentials check needed
        show_configuration()


if __name__ == '__main__':
    main()