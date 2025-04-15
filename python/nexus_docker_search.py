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
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if self.verbose:
                logging.error(f"HTTP Error {e.code}: {e.reason}")
            raise Exception(f"HTTP Error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            if self.verbose:
                logging.error(f"URL Error: {e.reason}")
            raise Exception(f"URL Error: {e.reason}")

    def search_images(self, patterns: List[str]) -> List[Dict[str, Any]]:
        """Search for Docker images matching the given patterns using the v1 search API.
        
        Args:
            patterns: List of regex patterns to match against image names
            
        Returns:
            List of matching images with their details
        """
        if self.verbose:
            logging.info(f"Searching for patterns: {patterns}")
            
        # Build search parameters
        params = {
            "repository": self.repository,
            "format": "docker"
        }
        
        # Add name pattern if only one pattern is provided
        if len(patterns) == 1:
            params["name"] = patterns[0]
            if self.verbose:
                logging.info(f"Using exact name pattern: {patterns[0]}")
        
        if self.verbose:
            logging.info("Fetching components from search API")
            logging.info(f"Parameters: {params}")
        
        try:
            # Get all components and filter by pattern if multiple patterns provided
            matching_images = []
            continuation_token = None
            
            while True:
                if continuation_token:
                    params["continuationToken"] = continuation_token
                    if self.verbose:
                        logging.info(f"Fetching next page with token: {continuation_token}")
                
                data = self._make_request(self.nexus_url, params)
                
                if self.verbose:
                    logging.info(f"Found {len(data.get('items', []))} components in current page")
                
                # Filter components by pattern if multiple patterns provided
                if len(patterns) > 1:
                    compiled_patterns = [re.compile(pattern) for pattern in patterns]
                    for component in data.get("items", []):
                        name = component.get("name", "")
                        if any(pattern.search(name) for pattern in compiled_patterns):
                            if self.verbose:
                                logging.info(f"Found matching image: {name}")
                            
                            # Get SHA256 from assets
                            sha256 = component.get("assets", [{}])[0].get("checksum", {}).get("sha256", "")
                            
                            matching_images.append({
                                "name": name,
                                "version": component.get("version", ""),
                                "sha256": sha256
                            })
                else:
                    # No need to filter if using exact name pattern
                    for component in data.get("items", []):
                        if self.verbose:
                            logging.info(f"Found image: {component.get('name', '')}")
                        
                        # Get SHA256 from assets
                        sha256 = component.get("assets", [{}])[0].get("checksum", {}).get("sha256", "")
                        
                        matching_images.append({
                            "name": component.get("name", ""),
                            "version": component.get("version", ""),
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
            
            return matching_images
            
        except Exception as e:
            if self.verbose:
                logging.error(f"Failed to search images: {e}")
            return []

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