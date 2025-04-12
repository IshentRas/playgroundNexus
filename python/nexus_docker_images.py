#!/usr/bin/env python3
import argparse
import json
from typing import List, Dict, Any
from collections import defaultdict

def filter_tags(tags: List[str], latest_digest: str, version_digest: str) -> List[str]:
    """Filter and sort tags for an image.
    
    Args:
        tags: List of tags to filter
        latest_digest: SHA256 digest of the latest tag
        version_digest: SHA256 digest of the version tag
        
    Returns:
        List of filtered and sorted tags
    """
    if not tags:
        return []
    
    # Separate latest tag from other tags
    version_tags = [tag for tag in tags if tag != "latest"]
    
    # Sort version tags numerically
    def sort_key(tag):
        try:
            return int(tag)
        except ValueError:
            return 0
            
    version_tags.sort(key=sort_key, reverse=True)
    
    # Take only the last 2 valid tags
    version_tags = version_tags[:2]
    
    # If latest tag exists and matches the highest version, include it
    if "latest" in tags and latest_digest and version_digest:
        if latest_digest == version_digest:
            return ["latest"] + version_tags
            
    return version_tags

def process_images(images: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Process a list of images and their tags.
    
    Args:
        images: List of image information from search results
        
    Returns:
        Dictionary with image names as keys and filtered tag lists as values
    """
    # Group images by name
    image_groups = defaultdict(list)
    for image in images:
        name = image["name"]
        version = image["version"]
        sha256 = image["sha256"]
        image_groups[name].append({"version": version, "sha256": sha256})
    
    # Process each group
    results = {}
    for name, versions in image_groups.items():
        # Get all versions and their digests
        tags = []
        latest_digest = None
        version_digest = None
        highest_version = None
        
        for version_info in versions:
            version = version_info["version"]
            sha256 = version_info["sha256"]
            tags.append(version)
            
            if version == "latest":
                latest_digest = sha256
            elif version.isdigit():
                version_num = int(version)
                if highest_version is None or version_num > highest_version:
                    highest_version = version_num
                    version_digest = sha256
        
        # Filter and sort tags
        filtered_tags = filter_tags(tags, latest_digest, version_digest)
        
        # Add to results
        results[name] = filtered_tags
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Process Docker images from Nexus search results")
    parser.add_argument("--input", "-i", required=True, help="Input JSON file from nexus_docker_search.py")
    parser.add_argument("--output", "-o", help="Output JSON file (default: stdout)")
    
    args = parser.parse_args()
    
    try:
        # Read search results from file
        with open(args.input, 'r') as f:
            search_results = json.load(f)
            
        # Process images
        results = process_images(search_results)
        
        # Output results
        output_json = json.dumps(results, indent=2)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output_json)
        else:
            print(output_json)
            
    except FileNotFoundError:
        print(f"Error: Input file '{args.input}' not found")
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in input file '{args.input}'")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()