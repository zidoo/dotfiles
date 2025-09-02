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
        region = boto3.Session().region_name or 'default'
    
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
    
    return f"/tmp/ec2_cache_{region}_{cred_hash}.json"


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
                                     usage='%(prog)s list [name_pattern] [options]')
    
    # Positional arguments
    parser.add_argument('command', choices=['list'],
                        help='Command to execute')
    parser.add_argument('name_pattern', nargs='?',
                        help='Filter instances by name (supports wildcards like *mongo*)')
    
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
    
    args = parser.parse_args()
    
    # Check credentials if not provided via arguments
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
            
            print_instances_table(filtered_instances)


if __name__ == '__main__':
    main()