#!/usr/bin/env python3
import urllib.request
import urllib.error
import urllib.parse
import base64
import re
import argparse
import ssl
import logging
from typing import List, Dict, Any
import json
from collections import defaultdict

class NexusDockerSearch:
    def __init__(self, nexus_url: str, repository: str, username: str = None, password: str = None, verify_ssl: bool = True, verbose: bool = False):
        """Initialize the Nexus Docker Search client.
        
        Args:
            nexus_url: Base URL of the Nexus server
            repository: Name of the Docker repository to search in
            username: Nexus username (optional)
            password: Nexus password (optional)
            verify_ssl: Whether to verify SSL certificates (default: True)
            verbose: Whether to enable verbose logging (default: False)
        """
        self.nexus_url = f"{nexus_url.rstrip('/')}/service/rest/v1/search"
        self.username = username
        self.password = password
        self.repository = repository
        self.verify_ssl = verify_ssl
        self.verbose = verbose
        
        # Set up logging
        if verbose:
            logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
            logging.info(f"Initializing Nexus Docker Search client")
            logging.info(f"URL: {self.nexus_url}")
            logging.info(f"Repository: {self.repository}")
            logging.info(f"Authentication: {'enabled' if username and password else 'disabled'}")
            logging.info(f"SSL Verification: {'enabled' if verify_ssl else 'disabled'}")
        
        # Create basic auth header if credentials are provided
        if username and password:
            credentials = f"{username}:{password}".encode('utf-8')
            self.auth_header = f"Basic {base64.b64encode(credentials).decode('utf-8')}"
        else:
            self.auth_header = None

    def _make_request(self, url: str, params: Dict[str, str] = None) -> Dict[str, Any]:
        """Make an HTTP GET request with authentication.
        
        Args:
            url: The URL to request
            params: Query parameters
            
        Returns:
            Parsed JSON response
        """
        # Add query parameters to URL
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
            
        if self.verbose:
            logging.info(f"Making request to: {url}")
            if params:
                logging.info(f"Query parameters: {params}")
            
        request = urllib.request.Request(url)
        if self.auth_header:
            request.add_header("Authorization", self.auth_header)
        
        # Create SSL context if needed
        context = None
        if not self.verify_ssl and url.startswith('https://'):
            context = ssl._create_unverified_context()
            if self.verbose:
                logging.warning("SSL certificate verification is disabled")
        
        try:
            with urllib.request.urlopen(request, context=context) as response:
                if self.verbose:
                    logging.info(f"Response status: {response.status}")
                response_data = response.read()
                if isinstance(response_data, bytes):
                    response_data = response_data.decode('utf-8')
                return json.loads(response_data)
        except urllib.error.HTTPError as e:
            if self.verbose:
                logging.error(f"HTTP Error {e.code}: {e.reason}")
            # For mock HTTPError objects, just re-raise
            if hasattr(e, 'fp') and e.fp is None:
                raise
            # For real HTTPError objects, recreate with all properties
            raise urllib.error.HTTPError(e.url, e.code, e.reason, e.headers, e.fp)
        except urllib.error.URLError as e:
            if self.verbose:
                logging.error(f"URL Error: {e.reason}")
            raise urllib.error.URLError(e.reason)
        except Exception as e:
            if self.verbose:
                logging.error(f"Error making request: {e}")
            raise Exception(str(e))

    def search_images(self, patterns: List[str]) -> Dict[str, List[str]]:
        """Search for Docker images matching the given patterns using the v1 search API.
        
        Args:
            patterns: List of regex patterns to match against image names
            
        Returns:
            Dictionary with image names as keys and filtered tag lists as values
        """
        if self.verbose:
            logging.info(f"Searching for patterns: {patterns}")
            
        # Build base search parameters
        base_params = {
            "repository": self.repository,
            "format": "docker"
        }
        
        try:
            # Get all components for each pattern
            matching_images = []
            seen_images = set()  # Track unique images by name:version
            
            for pattern in patterns:
                if self.verbose:
                    logging.info(f"Searching with pattern: {pattern}")
                
                # Add pattern to parameters
                params = base_params.copy()
                params["name"] = pattern
                
                continuation_token = None
                while True:
                    if continuation_token:
                        params["continuationToken"] = continuation_token
                        if self.verbose:
                            logging.info(f"Fetching next page with token: {continuation_token}")
                    
                    data = self._make_request(self.nexus_url, params)
                    
                    if self.verbose:
                        logging.info(f"Found {len(data.get('items', []))} components in current page")
                    
                    # Process components
                    for component in data.get("items", []):
                        name = component.get("name", "")
                        version = component.get("version", "")
                        image_key = f"{name}:{version}"
                        
                        # Skip if we've already seen this image:version
                        if image_key in seen_images:
                            if self.verbose:
                                logging.info(f"Skipping duplicate image: {image_key}")
                            continue
                        
                        seen_images.add(image_key)
                        if self.verbose:
                            logging.info(f"Found image: {name}")
                        
                        # Get SHA256 from assets
                        sha256 = component.get("assets", [{}])[0].get("checksum", {}).get("sha256", "")
                        
                        matching_images.append({
                            "name": name,
                            "version": version,
                            "sha256": sha256
                        })
                    
                    # Check if there are more results
                    continuation_token = data.get("continuationToken")
                    if not continuation_token:
                        if self.verbose:
                            logging.info("No more pages to fetch")
                        break
            
            if self.verbose:
                logging.info(f"Total matching images found: {len(matching_images)}")
            
            # Process and filter the images
            return self.process_images(matching_images)
            
        except Exception as e:
            if self.verbose:
                logging.error(f"Failed to search images: {e}")
            raise

    def filter_tags(self, tags: List[str], latest_digest: str, version_digest: str) -> List[str]:
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
        if "latest" in tags:
            if not version_tags or latest_digest == version_digest:
                return ["latest"] + version_tags
                
        return version_tags

    def process_images(self, images: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Process a list of images and their tags.
        
        Args:
            images: List of image information from search results
            
        Returns:
            Dictionary with image names as keys and filtered tag lists as values
        """
        if self.verbose:
            logging.info("Processing and filtering image tags")
            logging.info(f"Input images: {images}")
            
        # Group images by name
        image_groups = defaultdict(list)
        for image in images:
            name = image["name"]
            version = image["version"]
            sha256 = image["sha256"]
            image_groups[name].append({"version": version, "sha256": sha256})
            
        if self.verbose:
            logging.info(f"Image groups: {dict(image_groups)}")
        
        # Process each group
        results = {}
        for name, versions in image_groups.items():
            if self.verbose:
                logging.info(f"Processing tags for image: {name}")
                logging.info(f"Versions: {versions}")
                
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
                else:
                    try:
                        version_num = int(version)
                        if highest_version is None or version_num > highest_version:
                            highest_version = version_num
                            version_digest = sha256
                    except ValueError:
                        continue
            
            if self.verbose:
                logging.info(f"Tags: {tags}")
                logging.info(f"Latest digest: {latest_digest}")
                logging.info(f"Version digest: {version_digest}")
            
            # Filter and sort tags
            filtered_tags = self.filter_tags(tags, latest_digest, version_digest)
            if filtered_tags:
                results[name] = filtered_tags
                if self.verbose:
                    logging.info(f"Filtered tags for {name}: {filtered_tags}")
        
        if self.verbose:
            logging.info(f"Final results: {results}")
            
        return results

def main():
    parser = argparse.ArgumentParser(description="Search for Docker images in Nexus repository")
    parser.add_argument("--url", required=True, help="Nexus server URL")
    parser.add_argument("--repository", required=True, help="Docker repository name")
    parser.add_argument("--username", help="Nexus username")
    parser.add_argument("--password", help="Nexus password")
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL certificate verification")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("patterns", nargs="+", help="Regex patterns to match against image names")
    
    args = parser.parse_args()
    
    # Initialize client
    client = NexusDockerSearch(
        args.url,
        args.repository,
        args.username,
        args.password,
        not args.no_verify_ssl,
        args.verbose
    )
    
    # Search for images
    results = client.search_images(args.patterns)
    
    # Output results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
    else:
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main() 