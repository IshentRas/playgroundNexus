#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
from unittest.mock import patch, MagicMock
import json
import base64
import os
import sys
import urllib.error
import ssl

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python.nexus_docker_search import NexusDockerSearch

class TestNexusDockerSearch(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.nexus_url = "http://localhost:8081"
        self.repository = "my-private-docker-repo"
        self.username = "admin"
        self.password = "admin"
        
        # Mock responses
        self.mock_catalog_response = {
            "repositories": [
                "test/image1",
                "test/image2",
                "other/image3"
            ]
        }
        
        self.mock_tags_response = {
            "name": "test/image1",
            "tags": ["latest", "v1.0", "v1.1"]
        }
        
        self.mock_manifest_response = {
            "config": {
                "digest": "sha256:1234567890abcdef"
            }
        }

    def test_init_without_auth(self):
        """Test initialization without authentication."""
        client = NexusDockerSearch(self.nexus_url, self.repository)
        self.assertEqual(client.nexus_url, f"{self.nexus_url}/repository/{self.repository}")
        self.assertIsNone(client.username)
        self.assertIsNone(client.password)
        self.assertIsNone(client.auth_header)

    def test_init_with_auth(self):
        """Test initialization with authentication."""
        client = NexusDockerSearch(self.nexus_url, self.repository, self.username, self.password)
        self.assertEqual(client.nexus_url, f"{self.nexus_url}/repository/{self.repository}")
        self.assertEqual(client.username, self.username)
        self.assertEqual(client.password, self.password)
        self.assertIsNotNone(client.auth_header)

    @patch('urllib.request.urlopen')
    def test_make_request_without_auth(self, mock_urlopen):
        """Test making a request without authentication."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"test": "data"}).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        client = NexusDockerSearch(self.nexus_url, self.repository)
        response = client._make_request("http://test.com")
        
        # Verify request was made without auth header
        mock_urlopen.assert_called_once()
        request = mock_urlopen.call_args[0][0]
        self.assertNotIn("Authorization", request.headers)
        self.assertEqual(response, {"test": "data"})

    @patch('urllib.request.urlopen')
    def test_make_request_with_auth(self, mock_urlopen):
        """Test making a request with authentication."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"test": "data"}).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        client = NexusDockerSearch(self.nexus_url, self.repository, self.username, self.password)
        response = client._make_request("http://test.com")
        
        # Verify request was made with auth header
        mock_urlopen.assert_called_once()
        request = mock_urlopen.call_args[0][0]
        self.assertIn("Authorization", request.headers)
        self.assertEqual(response, {"test": "data"})

    @patch('urllib.request.urlopen')
    def test_search_images(self, mock_urlopen):
        """Test searching for images."""
        # Setup mock responses
        mock_response = MagicMock()
        mock_response.read.side_effect = [
            json.dumps(self.mock_catalog_response).encode('utf-8'),  # Catalog response
            json.dumps(self.mock_tags_response).encode('utf-8'),     # Tags for test/image1
            json.dumps(self.mock_manifest_response).encode('utf-8'), # Manifest for test/image1:latest
            json.dumps(self.mock_tags_response).encode('utf-8'),     # Tags for test/image2
            json.dumps(self.mock_manifest_response).encode('utf-8')  # Manifest for test/image2:latest
        ]
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        client = NexusDockerSearch(self.nexus_url, self.repository)
        results = client.search_images(["test/.*"])
        
        # Verify results
        self.assertEqual(len(results), 2)  # Should match test/image1 and test/image2
        self.assertEqual(results[0]["name"], "test/image1")
        self.assertEqual(results[0]["version"], "latest")
        self.assertEqual(results[0]["sha256"], "1234567890abcdef")
        self.assertEqual(results[1]["name"], "test/image2")
        self.assertEqual(results[1]["version"], "latest")
        self.assertEqual(results[1]["sha256"], "1234567890abcdef")

    @patch('urllib.request.urlopen')
    def test_get_image_tags(self, mock_urlopen):
        """Test getting tags for an image."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(self.mock_tags_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        client = NexusDockerSearch(self.nexus_url, self.repository)
        tags = client.get_image_tags("test/image1")
        
        # Verify tags
        self.assertEqual(tags, ["latest", "v1.0", "v1.1"])

    @patch('urllib.request.urlopen')
    def test_http_error_handling(self, mock_urlopen):
        """Test handling of HTTP errors."""
        # Setup mock to raise HTTPError
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://test.com", 404, "Not Found", {}, None
        )
        
        client = NexusDockerSearch(self.nexus_url, self.repository)
        with self.assertRaises(Exception) as context:
            client._make_request("http://test.com")
        
        self.assertIn("HTTP Error 404", str(context.exception))

    @patch('urllib.request.urlopen')
    def test_url_error_handling(self, mock_urlopen):
        """Test handling of URL errors."""
        # Setup mock to raise URLError
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        
        client = NexusDockerSearch(self.nexus_url, self.repository)
        with self.assertRaises(Exception) as context:
            client._make_request("http://test.com")
        
        self.assertIn("URL Error", str(context.exception))

if __name__ == '__main__':
    unittest.main() 