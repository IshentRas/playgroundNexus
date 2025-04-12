#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
import json
import os
import sys

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python.nexus_docker_images import filter_tags, process_images

class TestNexusDockerImages(unittest.TestCase):
	def test_filter_tags_empty(self):
		"""Test filter_tags with empty input"""
		self.assertEqual(filter_tags([], None, None), [])
		
	def test_filter_tags_latest_matches(self):
		"""Test filter_tags when latest matches highest version"""
		tags = ["latest", "2", "1"]
		latest_digest = "abc123"
		version_digest = "abc123"
		expected = ["latest", "2", "1"]
		self.assertEqual(filter_tags(tags, latest_digest, version_digest), expected)
		
	def test_filter_tags_latest_no_match(self):
		"""Test filter_tags when latest doesn't match highest version"""
		tags = ["latest", "2", "1"]
		latest_digest = "abc123"
		version_digest = "def456"
		expected = ["2", "1"]
		self.assertEqual(filter_tags(tags, latest_digest, version_digest), expected)
		
	def test_filter_tags_no_latest(self):
		"""Test filter_tags without latest tag"""
		tags = ["2", "1"]
		latest_digest = None
		version_digest = "abc123"
		expected = ["2", "1"]
		self.assertEqual(filter_tags(tags, latest_digest, version_digest), expected)
		
	def test_process_images(self):
		"""Test process_images with sample data"""
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
		self.assertEqual(process_images(images), expected)

	def test_file_io(self):
		"""Test file input/output functionality"""
		# Create test data
		test_images = [
			{"name": "test/image", "version": "1", "sha256": "abc123"},
			{"name": "test/image", "version": "2", "sha256": "def456"},
			{"name": "test/image", "version": "latest", "sha256": "def456"}
		]

		# Create temporary input file
		with open("test.json", "w") as f:
			json.dump(test_images, f)

		try:
			# Read and process the file
			with open("test.json", "r") as f:
				images = json.load(f)

			result = process_images(images)

			# Verify output format
			expected_tags = {
				"test/image": ["latest", "2", "1"]
			}

			self.assertEqual(result, expected_tags)
		finally:
			# Clean up
			if os.path.exists("test.json"):
				os.remove("test.json")

if __name__ == '__main__':
	unittest.main() 