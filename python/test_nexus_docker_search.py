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
import urllib.parse

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python.nexus_docker_search import NexusDockerSearch

class TestNexusDockerSearch(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.nexus_url = "http://nexus.example.com"
        self.repository = "docker-hosted"
        self.username = "admin"
        self.password = "password"
        self.verbose = True
        
        # Mock responses for single pattern search
        self.mock_single_pattern_response = {
            "items": [
                {
                    "name": "test/image1",
                    "version": "latest",
                    "assets": [
                        {
                            "checksum": {
                                "sha256": "abc123"
                            }
                        }
                    ]
                },
                {
                    "name": "test/image1",
                    "version": "2",
                    "assets": [
                        {
                            "checksum": {
                                "sha256": "abc123"
                            }
                        }
                    ]
                },
                {
                    "name": "test/image1",
                    "version": "1",
                    "assets": [
                        {
                            "checksum": {
                                "sha256": "def456"
                            }
                        }
                    ]
                }
            ]
        }
        
        # Mock responses for multiple pattern search
        self.mock_pattern1_response = {
            "items": [
                {
                    "name": "test/image1",
                    "version": "latest",
                    "assets": [
                        {
                            "checksum": {
                                "sha256": "abc123"
                            }
                        }
                    ]
                }
            ]
        }
        
        self.mock_pattern2_response = {
            "items": [
                {
                    "name": "test/image2",
                    "version": "latest",
                    "assets": [
                        {
                            "checksum": {
                                "sha256": "xyz789"
                            }
                        }
                    ]
                },
                {
                    "name": "test/image2",
                    "version": "1",
                    "assets": [
                        {
                            "checksum": {
                                "sha256": "xyz789"
                            }
                        }
                    ]
                }
            ]
        }

    def test_init_without_auth(self):
        """Test initialization without authentication."""
        client = NexusDockerSearch(self.nexus_url, self.repository)
        self.assertEqual(client.nexus_url, f"{self.nexus_url}/service/rest/v1/search")
        self.assertIsNone(client.username)
        self.assertIsNone(client.password)
        self.assertIsNone(client.auth_header)

    def test_init_with_auth(self):
        """Test initialization with authentication."""
        client = NexusDockerSearch(self.nexus_url, self.repository, self.username, self.password)
        self.assertEqual(client.nexus_url, f"{self.nexus_url}/service/rest/v1/search")
        self.assertEqual(client.username, self.username)
        self.assertEqual(client.password, self.password)
        self.assertIsNotNone(client.auth_header)

    def test_filter_tags_empty(self):
        """Test filter_tags with empty input"""
        client = NexusDockerSearch(self.nexus_url, self.repository)
        self.assertEqual(client.filter_tags([], None, None), [])

    def test_filter_tags_latest_matches(self):
        """Test filter_tags when latest matches highest version"""
        client = NexusDockerSearch(self.nexus_url, self.repository)
        tags = ["latest", "2", "1"]
        latest_digest = "abc123"
        version_digest = "abc123"
        expected = ["latest", "2", "1"]
        self.assertEqual(client.filter_tags(tags, latest_digest, version_digest), expected)

    def test_filter_tags_latest_no_match(self):
        """Test filter_tags when latest doesn't match highest version"""
        client = NexusDockerSearch(self.nexus_url, self.repository)
        tags = ["latest", "2", "1"]
        latest_digest = "abc123"
        version_digest = "def456"
        expected = ["2", "1"]
        self.assertEqual(client.filter_tags(tags, latest_digest, version_digest), expected)

    def test_filter_tags_no_latest(self):
        """Test filter_tags without latest tag"""
        client = NexusDockerSearch(self.nexus_url, self.repository)
        tags = ["2", "1"]
        latest_digest = None
        version_digest = "abc123"
        expected = ["2", "1"]
        self.assertEqual(client.filter_tags(tags, latest_digest, version_digest), expected)

    def test_process_images(self):
        """Test process_images with sample data"""
        client = NexusDockerSearch(self.nexus_url, self.repository)
        images = [
            {"name": "image1", "version": "latest", "sha256": "abc123"},
            {"name": "image1", "version": "2", "sha256": "abc123"},
            {"name": "image1", "version": "1", "sha256": "def456"},
            {"name": "image2", "version": "latest", "sha256": "xyz789"},
            {"name": "image2", "version": "1", "sha256": "xyz789"}
        ]
        expected = {
            "image1": ["latest", "2", "1"],
            "image2": ["latest", "1"]
        }
        self.assertEqual(client.process_images(images), expected)

    @patch('urllib.request.urlopen')
    def test_search_images_single_pattern(self, mock_urlopen):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(self.mock_single_pattern_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Initialize client
        client = NexusDockerSearch(
            self.nexus_url,
            self.repository,
            self.username,
            self.password,
            verbose=self.verbose
        )
        
        # Test single pattern search
        results = client.search_images(["test/image1"])
        
        # Verify results
        self.assertEqual(len(results), 3)
        
        # Verify first image
        self.assertEqual(results[0]["name"], "test/image1")
        self.assertEqual(results[0]["version"], "latest")
        self.assertEqual(results[0]["sha256"], "abc123")
        
        # Verify URL was called with correct parameters
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args[0][0]
        parsed_url = urllib.parse.urlparse(call_args.full_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        self.assertEqual(query_params["name"][0], "test/image1")
        self.assertEqual(query_params["repository"][0], "docker-hosted")
        self.assertEqual(query_params["format"][0], "docker")

    @patch('urllib.request.urlopen')
    def test_search_images_multiple_patterns(self, mock_urlopen):
        # Setup mock responses for each pattern
        mock_response = MagicMock()
        mock_response.read.side_effect = [
            json.dumps(self.mock_pattern1_response).encode('utf-8'),
            json.dumps(self.mock_pattern2_response).encode('utf-8')
        ]
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Initialize client
        client = NexusDockerSearch(
            self.nexus_url,
            self.repository,
            self.username,
            self.password,
            verbose=self.verbose
        )
        
        # Test multiple pattern search
        results = client.search_images(["test/image1", "test/image2"])
        
        # Verify results
        self.assertEqual(len(results), 3)
        
        # Verify first image
        self.assertEqual(results[0]["name"], "test/image1")
        self.assertEqual(results[0]["version"], "latest")
        self.assertEqual(results[0]["sha256"], "abc123")
        
        # Verify URL was called twice with correct parameters
        self.assertEqual(mock_urlopen.call_count, 2)
        
        # First call
        call_args = mock_urlopen.call_args_list[0][0][0]
        parsed_url = urllib.parse.urlparse(call_args.full_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        self.assertEqual(query_params["name"][0], "test/image1")
        self.assertEqual(query_params["repository"][0], "docker-hosted")
        self.assertEqual(query_params["format"][0], "docker")
        
        # Second call
        call_args = mock_urlopen.call_args_list[1][0][0]
        parsed_url = urllib.parse.urlparse(call_args.full_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        self.assertEqual(query_params["name"][0], "test/image2")
        self.assertEqual(query_params["repository"][0], "docker-hosted")
        self.assertEqual(query_params["format"][0], "docker")

    @patch('urllib.request.urlopen')
    def test_search_and_filter_images(self, mock_urlopen):
        """Test combined search and filter functionality"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(self.mock_single_pattern_response).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Initialize client
        client = NexusDockerSearch(
            self.nexus_url,
            self.repository,
            self.username,
            self.password,
            verbose=self.verbose
        )
        
        # Test search and filter
        results = client.search_and_filter_images(["test/image1"])
        
        # Verify filtered results
        expected = {
            "test/image1": ["latest", "2", "1"]
        }
        self.assertEqual(results, expected)
        
        # Verify URL was called with correct parameters
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args[0][0]
        parsed_url = urllib.parse.urlparse(call_args.full_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        self.assertEqual(query_params["name"][0], "test/image1")
        self.assertEqual(query_params["repository"][0], "docker-hosted")
        self.assertEqual(query_params["format"][0], "docker")

    @patch('urllib.request.urlopen')
    def test_search_images_no_matches(self, mock_urlopen):
        # Setup mock response with no matches
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"items": []}).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Initialize client
        client = NexusDockerSearch(
            self.nexus_url,
            self.repository,
            self.username,
            self.password,
            verbose=self.verbose
        )
        
        # Test search with no matches
        results = client.search_images(["nonexistent/image"])
        
        # Verify no results
        self.assertEqual(len(results), 0)
        
        # Verify URL was called with correct parameters
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args[0][0]
        parsed_url = urllib.parse.urlparse(call_args.full_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        self.assertEqual(query_params["name"][0], "nonexistent/image")
        self.assertEqual(query_params["repository"][0], "docker-hosted")
        self.assertEqual(query_params["format"][0], "docker")

    @patch('urllib.request.urlopen')
    def test_search_images_error_handling(self, mock_urlopen):
        # Setup mock to raise an exception
        mock_urlopen.side_effect = Exception("Test error")
        
        # Initialize client
        client = NexusDockerSearch(
            self.nexus_url,
            self.repository,
            self.username,
            self.password,
            verbose=self.verbose
        )
        
        # Test error handling
        results = client.search_images(["test/image"])
        
        # Verify empty results on error
        self.assertEqual(len(results), 0)

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