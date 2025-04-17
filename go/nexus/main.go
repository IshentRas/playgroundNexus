package main

import (
	"crypto/tls"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
)

// NexusDockerSearch represents a client for searching Docker images in a Nexus repository
type NexusDockerSearch struct {
	nexusURL   string
	repository string
	username   string
	password   string
	verifySSL  bool
	verbose    bool
	authHeader string
	httpClient *http.Client
}

// NewNexusDockerSearch creates a new NexusDockerSearch client
func NewNexusDockerSearch(nexusURL, repository, username, password string, verifySSL, verbose bool) *NexusDockerSearch {
	// Create HTTP client with SSL configuration
	transport := &http.Transport{
		TLSClientConfig: &tls.Config{
			InsecureSkipVerify: !verifySSL,
		},
	}
	client := &http.Client{Transport: transport}

	// Create basic auth header if credentials are provided
	var authHeader string
	if username != "" && password != "" {
		auth := username + ":" + password
		authHeader = "Basic " + base64.StdEncoding.EncodeToString([]byte(auth))
	}

	return &NexusDockerSearch{
		nexusURL:   strings.TrimRight(nexusURL, "/") + "/service/rest/v1/search",
		repository: repository,
		username:   username,
		password:   password,
		verifySSL:  verifySSL,
		verbose:    verbose,
		authHeader: authHeader,
		httpClient: client,
	}
}

// makeRequest performs an HTTP GET request with authentication
func (n *NexusDockerSearch) makeRequest(url string, params map[string]string) (map[string]interface{}, error) {
	// Add query parameters to URL
	if len(params) > 0 {
		query := make([]string, 0, len(params))
		for k, v := range params {
			query = append(query, fmt.Sprintf("%s=%s", k, v))
		}
		url = url + "?" + strings.Join(query, "&")
	}

	if n.verbose {
		fmt.Printf("Making request to: %s\n", url)
		if len(params) > 0 {
			fmt.Printf("Query parameters: %v\n", params)
		}
	}

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %v", err)
	}

	if n.authHeader != "" {
		req.Header.Add("Authorization", n.authHeader)
	}

	resp, err := n.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP error %d: %s", resp.StatusCode, resp.Status)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %v", err)
	}

	var result map[string]interface{}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to parse JSON response: %v", err)
	}

	return result, nil
}

// SearchImages searches for Docker images matching the given patterns
func (n *NexusDockerSearch) SearchImages(patterns []string) (map[string][]string, error) {
	if n.verbose {
		fmt.Printf("Searching for patterns: %v\n", patterns)
	}

	// Build base search parameters
	baseParams := map[string]string{
		"repository": n.repository,
		"format":     "docker",
	}

	// Get all components for each pattern
	matchingImages := make([]map[string]string, 0)
	seenImages := make(map[string]bool) // Track unique images by name:version

	for _, pattern := range patterns {
		if n.verbose {
			fmt.Printf("Searching with pattern: %s\n", pattern)
		}

		// Add pattern to parameters
		params := make(map[string]string)
		for k, v := range baseParams {
			params[k] = v
		}
		params["name"] = pattern

		continuationToken := ""
		for {
			if continuationToken != "" {
				params["continuationToken"] = continuationToken
				if n.verbose {
					fmt.Printf("Fetching next page with token: %s\n", continuationToken)
				}
			}

			data, err := n.makeRequest(n.nexusURL, params)
			if err != nil {
				return nil, fmt.Errorf("search failed: %v", err)
			}

			items, ok := data["items"].([]interface{})
			if !ok {
				return nil, fmt.Errorf("invalid response format: items not found")
			}

			if n.verbose {
				fmt.Printf("Found %d components in current page\n", len(items))
			}

			// Process components
			for _, item := range items {
				component, ok := item.(map[string]interface{})
				if !ok {
					continue
				}

				name, _ := component["name"].(string)
				version, _ := component["version"].(string)
				imageKey := name + ":" + version

				// Skip if we've already seen this image:version
				if seenImages[imageKey] {
					if n.verbose {
						fmt.Printf("Skipping duplicate image: %s\n", imageKey)
					}
					continue
				}

				seenImages[imageKey] = true
				if n.verbose {
					fmt.Printf("Found image: %s\n", name)
				}

				// Get SHA256 from assets
				assets, _ := component["assets"].([]interface{})
				var sha256 string
				if len(assets) > 0 {
					asset, _ := assets[0].(map[string]interface{})
					checksum, _ := asset["checksum"].(map[string]interface{})
					sha256, _ = checksum["sha256"].(string)
				}

				matchingImages = append(matchingImages, map[string]string{
					"name":    name,
					"version": version,
					"sha256":  sha256,
				})
			}

			// Check if there are more results
			if token, ok := data["continuationToken"].(string); ok && token != "" {
				continuationToken = token
			} else {
				if n.verbose {
					fmt.Println("No more pages to fetch")
				}
				break
			}
		}
	}

	if n.verbose {
		fmt.Printf("Total matching images found: %d\n", len(matchingImages))
	}

	// Process and filter the images
	return n.processImages(matchingImages)
}

// filterTags filters and sorts tags for an image
func (n *NexusDockerSearch) filterTags(tags []string, latestDigest, versionDigest string) []string {
	if len(tags) == 0 {
		return nil
	}

	// Separate latest tag from other tags
	var versionTags []string
	for _, tag := range tags {
		if tag != "latest" {
			versionTags = append(versionTags, tag)
		}
	}

	// Sort version tags numerically
	sort.Slice(versionTags, func(i, j int) bool {
		numI, errI := strconv.Atoi(versionTags[i])
		numJ, errJ := strconv.Atoi(versionTags[j])
		if errI != nil || errJ != nil {
			return false
		}
		return numI > numJ
	})

	// Take only the last 2 valid tags
	if len(versionTags) > 2 {
		versionTags = versionTags[:2]
	}

	// If latest tag exists and matches the highest version, include it
	for _, tag := range tags {
		if tag == "latest" && latestDigest != "" && versionDigest != "" {
			if latestDigest == versionDigest {
				return append([]string{"latest"}, versionTags...)
			}
		}
	}

	return versionTags
}

// processImages processes a list of images and their tags
func (n *NexusDockerSearch) processImages(images []map[string]string) (map[string][]string, error) {
	if n.verbose {
		fmt.Println("Processing and filtering image tags")
	}

	// Group images by name
	imageGroups := make(map[string][]map[string]string)
	for _, image := range images {
		name := image["name"]
		imageGroups[name] = append(imageGroups[name], image)
	}

	// Process each group
	results := make(map[string][]string)
	for name, versions := range imageGroups {
		if n.verbose {
			fmt.Printf("Processing tags for image: %s\n", name)
		}

		// Get all versions and their digests
		var tags []string
		var latestDigest, versionDigest string
		var highestVersion int

		for _, versionInfo := range versions {
			version := versionInfo["version"]
			sha256 := versionInfo["sha256"]
			tags = append(tags, version)

			if version == "latest" {
				latestDigest = sha256
			} else {
				if versionNum, err := strconv.Atoi(version); err == nil {
					if versionNum > highestVersion {
						highestVersion = versionNum
						versionDigest = sha256
					}
				}
			}
		}

		// Filter and sort tags
		filteredTags := n.filterTags(tags, latestDigest, versionDigest)
		if len(filteredTags) > 0 {
			results[name] = filteredTags
		}
	}

	return results, nil
}

func main() {
	// Parse command line arguments
	url := flag.String("url", "", "Nexus server URL")
	repository := flag.String("repository", "", "Docker repository name")
	username := flag.String("username", "", "Nexus username")
	password := flag.String("password", "", "Nexus password")
	noVerifySSL := flag.Bool("no-verify-ssl", false, "Disable SSL certificate verification")
	verbose := flag.Bool("verbose", false, "Enable verbose logging")
	output := flag.String("output", "", "Output file path")
	flag.Parse()

	patterns := flag.Args()
	if len(patterns) == 0 {
		fmt.Println("Error: at least one pattern is required")
		os.Exit(1)
	}

	if *url == "" || *repository == "" {
		fmt.Println("Error: --url and --repository are required")
		os.Exit(1)
	}

	// Initialize client
	client := NewNexusDockerSearch(*url, *repository, *username, *password, !*noVerifySSL, *verbose)

	// Search for images
	results, err := client.SearchImages(patterns)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}

	// Output results
	jsonData, err := json.MarshalIndent(results, "", "  ")
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}

	if *output != "" {
		if err := os.WriteFile(*output, jsonData, 0644); err != nil {
			fmt.Printf("Error writing to file: %v\n", err)
			os.Exit(1)
		}
	} else {
		fmt.Println(string(jsonData))
	}
}
