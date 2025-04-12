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
        self.nexus_url = f"{nexus_url.rstrip('/')}/repository/{repository}"
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
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if self.verbose:
                logging.error(f"HTTP Error {e.code}: {e.reason}")
            raise Exception(f"HTTP Error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            if self.verbose:
                logging.error(f"URL Error: {e.reason}")
            raise Exception(f"URL Error: {e.reason}")

    def get_image_tags(self, image_name: str) -> List[str]:
        """Get all tags for a specific image.
        
        Args:
            image_name: Name of the Docker image
            
        Returns:
            List of tags for the image
        """
        if self.verbose:
            logging.info(f"Fetching tags for image: {image_name}")
            
        url = f"{self.nexus_url}/v2/{image_name}/tags/list"
        
        try:
            data = self._make_request(url)
            tags = data.get("tags", [])
            
            if self.verbose:
                logging.info(f"Found {len(tags)} tags for {image_name}")
            
            return tags
        except Exception as e:
            if self.verbose:
                logging.error(f"Failed to get tags for {image_name}: {e}")
            return []

    def search_images(self, patterns: List[str]) -> List[Dict[str, Any]]:
        """Search for Docker images matching the given patterns using the v2 catalog API.
        
        Args:
            patterns: List of regex patterns to match against image names
            
        Returns:
            List of matching images with their details
        """
        if self.verbose:
            logging.info(f"Searching for patterns: {patterns}")
            
        # Compile regex patterns
        compiled_patterns = [re.compile(pattern) for pattern in patterns]
        
        # Get catalog of all images
        url = f"{self.nexus_url}/v2/_catalog"
        if self.verbose:
            logging.info("Fetching catalog of images")
            logging.info(f"Trying to access Docker Registry V2 API at: {url}")
        
        try:
            catalog = self._make_request(url)
            if self.verbose:
                logging.info(f"Found {len(catalog.get('repositories', []))} images in catalog")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                logging.error(f"Failed to access Docker Registry V2 API at {url}")
                logging.error("This suggests that the Nexus server might not be configured to expose the Docker Registry V2 API")
                logging.error("Please check that:")
                logging.error("1. The Nexus server has Docker Registry V2 API enabled")
                logging.error("2. The URL is correct (should be {base_url}/{repository}/v2/_catalog)")
                logging.error("3. The repository is properly configured for Docker Registry V2")
            else:
                logging.error(f"HTTP Error {e.code}: {e.reason}")
            return []
        except Exception as e:
            if self.verbose:
                logging.error(f"Failed to fetch catalog: {e}")
            return []
        
        matching_images = []
        for image_name in catalog.get("repositories", []):
            # Skip images that don't match any pattern
            if not any(pattern.search(image_name) for pattern in compiled_patterns):
                if self.verbose:
                    logging.info(f"Skipping non-matching image: {image_name}")
                continue
                
            if self.verbose:
                logging.info(f"Found matching image: {image_name}")
            
            # Get tags for this image
            tags = self.get_image_tags(image_name)
            if not tags:
                if self.verbose:
                    logging.info(f"No tags found for {image_name}, skipping")
                continue
            
            # Get SHA256 for each tag
            for tag in tags:
                try:
                    # Get manifest for the tag
                    manifest_url = f"{self.nexus_url}/v2/{image_name}/manifests/{tag}"
                    manifest = self._make_request(manifest_url)
                    
                    # Extract SHA256 from manifest
                    sha256 = manifest.get("config", {}).get("digest", "").replace("sha256:", "")
                    
                    matching_images.append({
                        "name": image_name,
                        "version": tag,
                        "sha256": sha256
                    })
                except Exception as e:
                    if self.verbose:
                        logging.warning(f"Failed to get manifest for {image_name}:{tag}: {e}")
        
        if self.verbose:
            logging.info(f"Total matching images found: {len(matching_images)}")
        
        return matching_images

def main():
    parser = argparse.ArgumentParser(description="Search for Docker images in Nexus using regex patterns")
    parser.add_argument("--url", default="http://localhost:8081", help="Nexus server URL")
    parser.add_argument("--username", help="Nexus username (optional)")
    parser.add_argument("--password", help="Nexus password (optional)")
    parser.add_argument("--repository", default="my-private-docker-repo", help="Docker repository name")
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL certificate verification")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("patterns", nargs="+", help="Regex patterns to match against image names")
    parser.add_argument("--output", "-o", help="Output file for results (JSON format)")
    
    args = parser.parse_args()
    
    try:
        if args.verbose:
            print("Starting Nexus Docker Search...")
            print(f"URL: {args.url}")
            print(f"Repository: {args.repository}")
            print(f"Patterns: {args.patterns}")
            if args.no_verify_ssl:
                print("SSL certificate verification is disabled")
            if args.username and args.password:
                print("Authentication is enabled")
            else:
                print("Authentication is disabled")
        
        client = NexusDockerSearch(
            args.url, 
            args.repository,
            args.username, 
            args.password, 
            verify_ssl=not args.no_verify_ssl,
            verbose=args.verbose
        )
        results = client.search_images(args.patterns)
        
        # Print results
        print(f"\nFound {len(results)} matching images:")
        for result in results:
            print(f"\nImage: {result['name']}")
            print(f"Version: {result['version']}")
            print(f"SHA256: {result['sha256']}")
        
        # Save to file if specified
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\nResults saved to {args.output}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 