package main

import (
	"crypto/tls"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

// NexusDockerSearch represents a client for searching Docker images in Nexus
type NexusDockerSearch struct {
	nexusURL    string
	repository  string
	username    string
	password    string
	verifySSL   bool
	verbose     bool
	authHeader  string
	httpClient  *http.Client
}

// SearchResult represents a Docker image search result
type SearchResult struct {
	Name    string `json:"name"`
	Version string `json:"version"`
	SHA256  string `json:"sha256"`
}

// ImageResult represents the final filtered result for each image
type ImageResult map[string][]string

// NexusResponse represents the response from Nexus search API
type NexusResponse struct {
	Items             []Component `json:"items"`
	ContinuationToken string     `json:"continuationToken"`
}

// Component represents a Nexus component
type Component struct {
	Name    string  `json:"name"`
	Version string  `json:"version"`
	Assets  []Asset `json:"assets"`
	Tags    []string
}

// Asset represents a Nexus asset
type Asset struct {
	Checksum Checksum `json:"checksum"`
}

// Checksum represents a Nexus asset checksum
type Checksum struct {
	SHA256 string `json:"sha256"`
}

// NewNexusDockerSearch creates a new NexusDockerSearch client
func NewNexusDockerSearch(nexusURL, repository, username, password string, verifySSL, verbose bool) *NexusDockerSearch {
	client := &NexusDockerSearch{
		nexusURL:   strings.TrimRight(nexusURL, "/") + "/service/rest/v1/search",
		repository: repository,
		username:   username,
		password:   password,
		verifySSL:  verifySSL,
		verbose:    verbose,
	}

	// Set up HTTP client with SSL verification settings
	tr := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: !verifySSL},
	}
	client.httpClient = &http.Client{Transport: tr}

	// Set up basic auth if credentials are provided
	if username != "" && password != "" {
		credentials := base64.StdEncoding.EncodeToString([]byte(fmt.Sprintf("%s:%s", username, password)))
		client.authHeader = fmt.Sprintf("Basic %s", credentials)
	}

	if verbose {
		log.Printf("Initializing Nexus Docker Search client")
		log.Printf("URL: %s", client.nexusURL)
		log.Printf("Repository: %s", client.repository)
		log.Printf("Authentication: %s", map[bool]string{true: "enabled", false: "disabled"}[username != "" && password != ""])
		log.Printf("SSL Verification: %s", map[bool]string{true: "enabled", false: "disabled"}[verifySSL])
	}

	return client
}

// makeRequest makes an HTTP GET request with authentication
func (n *NexusDockerSearch) makeRequest(params url.Values) (*NexusResponse, error) {
	reqURL := n.nexusURL
	if len(params) > 0 {
		reqURL += "?" + params.Encode()
	}

	if n.verbose {
		log.Printf("Making request to: %s", reqURL)
		if len(params) > 0 {
			log.Printf("Query parameters: %v", params)
		}
	}

	req, err := http.NewRequest("GET", reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %v", err)
	}

	if n.authHeader != "" {
		req.Header.Set("Authorization", n.authHeader)
	}

	resp, err := n.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %v", err)
	}
	defer resp.Body.Close()

	if n.verbose {
		log.Printf("Response status: %d", resp.StatusCode)
	}

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("HTTP error %d: %s", resp.StatusCode, string(body))
	}

	var result NexusResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %v", err)
	}

	return &result, nil
}

// filterTags filters and sorts tags for an image
func (n *NexusDockerSearch) filterTags(tags []string, latestDigest, versionDigest string) []string {
	if len(tags) == 0 {
		return tags
	}

	// Separate latest tag from version tags
	var versionTags []string
	hasLatest := false
	for _, tag := range tags {
		if tag == "latest" {
			hasLatest = true
		} else {
			versionTags = append(versionTags, tag)
		}
	}

	// Sort version tags numerically
	sort.Slice(versionTags, func(i, j int) bool {
		// Try to convert to integers for comparison
		iNum, iErr := strconv.Atoi(versionTags[i])
		jNum, jErr := strconv.Atoi(versionTags[j])
		
		// If both are numbers, compare numerically
		if iErr == nil && jErr == nil {
			return iNum > jNum
		}
		// Otherwise, use string comparison
		return versionTags[i] > versionTags[j]
	})

	// Take only the last 2 valid tags
	if len(versionTags) > 2 {
		versionTags = versionTags[:2]
	}

	// If latest tag exists and matches the highest version, include it
	if hasLatest && latestDigest != "" && versionDigest != "" && latestDigest == versionDigest {
		return append([]string{"latest"}, versionTags...)
	}

	return versionTags
}

// processImages processes a list of images and their tags
func (n *NexusDockerSearch) processImages(images []SearchResult) ImageResult {
	if n.verbose {
		log.Printf("Processing and filtering image tags")
	}

	// Group images by name
	imageGroups := make(map[string][]SearchResult)
	for _, img := range images {
		imageGroups[img.Name] = append(imageGroups[img.Name], img)
	}

	// Process each group
	results := make(ImageResult)
	for name, versions := range imageGroups {
		if n.verbose {
			log.Printf("Processing tags for image: %s", name)
		}

		// Get all versions and their digests
		var tags []string
		var latestDigest, versionDigest string
		var highestVersion int = -1

		for _, ver := range versions {
			tags = append(tags, ver.Version)

			if ver.Version == "latest" {
				latestDigest = ver.SHA256
			} else if num, err := strconv.Atoi(ver.Version); err == nil {
				if num > highestVersion {
					highestVersion = num
					versionDigest = ver.SHA256
				}
			}
		}

		// Filter and sort tags
		filteredTags := n.filterTags(tags, latestDigest, versionDigest)

		if n.verbose {
			log.Printf("Filtered tags for %s: %v", name, filteredTags)
		}

		results[name] = filteredTags
	}

	return results
}

// SearchImages searches for Docker images matching the given patterns
func (n *NexusDockerSearch) SearchImages(patterns []string) ([]SearchResult, error) {
	if n.verbose {
		log.Printf("Searching for patterns: %v", patterns)
	}

	var matchingImages []SearchResult
	seenImages := make(map[string]bool)

	for _, pattern := range patterns {
		if n.verbose {
			log.Printf("Searching with pattern: %s", pattern)
		}

		params := url.Values{
			"repository": {n.repository},
			"format":     {"docker"},
			"name":       {pattern},
		}

		continuationToken := ""
		for {
			if continuationToken != "" {
				params.Set("continuationToken", continuationToken)
				if n.verbose {
					log.Printf("Fetching next page with token: %s", continuationToken)
				}
			}

			data, err := n.makeRequest(params)
			if err != nil {
				if n.verbose {
					log.Printf("Failed to search images: %v", err)
				}
				return nil, err
			}

			if n.verbose {
				log.Printf("Found %d components in current page", len(data.Items))
			}

			for _, component := range data.Items {
				imageKey := fmt.Sprintf("%s:%s", component.Name, component.Version)

				if seenImages[imageKey] {
					if n.verbose {
						log.Printf("Skipping duplicate image: %s", imageKey)
					}
					continue
				}

				seenImages[imageKey] = true
				if n.verbose {
					log.Printf("Found image: %s", component.Name)
				}

				var sha256 string
				if len(component.Assets) > 0 {
					sha256 = component.Assets[0].Checksum.SHA256
				}

				matchingImages = append(matchingImages, SearchResult{
					Name:    component.Name,
					Version: component.Version,
					SHA256:  sha256,
				})
			}

			if data.ContinuationToken == "" {
				if n.verbose {
					log.Printf("No more pages to fetch")
				}
				break
			}
			continuationToken = data.ContinuationToken
		}
	}

	if n.verbose {
		log.Printf("Total matching images found: %d", len(matchingImages))
	}

	return matchingImages, nil
}

// SearchAndFilterImages searches for Docker images and filters their tags in one operation
func (n *NexusDockerSearch) SearchAndFilterImages(patterns []string) (ImageResult, error) {
	if n.verbose {
		log.Printf("Starting combined search and filter operation")
	}

	// First search for images
	images, err := n.SearchImages(patterns)
	if err != nil {
		return nil, err
	}

	if len(images) == 0 {
		if n.verbose {
			log.Printf("No images found matching the patterns")
		}
		return ImageResult{}, nil
	}

	// Then process and filter the tags
	return n.processImages(images), nil
}

func main() {
	// Define a custom flag set to stop parsing at first non-flag argument
	flagSet := flag.NewFlagSet("nexus-docker-search", flag.ExitOnError)

	nexusURL := flagSet.String("url", "http://localhost:8081", "Nexus server URL")
	repository := flagSet.String("repository", "my-private-docker-repo", "Docker repository name")
	username := flagSet.String("username", "", "Nexus username")
	password := flagSet.String("password", "", "Nexus password")
	verifySSL := flagSet.Bool("verify-ssl", true, "Verify SSL certificates")
	verbose := flagSet.Bool("verbose", false, "Enable verbose logging")
	raw := flagSet.Bool("raw", false, "Output raw search results without filtering")
	outputFile := flagSet.String("o", "", "Output file for results (JSON format)")

	// Parse flags until first non-flag argument
	if err := flagSet.Parse(os.Args[1:]); err != nil {
		fmt.Printf("Error parsing flags: %v\n", err)
		flagSet.Usage()
		os.Exit(1)
	}

	// Set up logging
	if *verbose {
		log.SetFlags(log.LstdFlags | log.Lmicroseconds)
		log.SetPrefix("DEBUG: ")
	}

	if *nexusURL == "" {
		fmt.Println("Error: Nexus URL is required")
		flagSet.Usage()
		os.Exit(1)
	}

	// Get patterns from remaining arguments
	patterns := flagSet.Args()
	if len(patterns) == 0 {
		fmt.Println("Error: At least one search pattern is required")
		flagSet.Usage()
		os.Exit(1)
	}

	if *verbose {
		fmt.Println("Starting Nexus Docker Search...")
		fmt.Printf("URL: %s\n", *nexusURL)
		fmt.Printf("Repository: %s\n", *repository)
		fmt.Printf("Patterns: %v\n", patterns)
		if !*verifySSL {
			fmt.Println("SSL certificate verification is disabled")
		}
		if *username != "" && *password != "" {
			fmt.Println("Authentication is enabled")
		} else {
			fmt.Println("Authentication is disabled")
		}
		if *outputFile != "" {
			fmt.Printf("Output will be saved to: %s\n", *outputFile)
		}
	}

	client := NewNexusDockerSearch(*nexusURL, *repository, *username, *password, *verifySSL, *verbose)

	var output interface{}
	if *raw {
		// Get raw search results
		results, err := client.SearchImages(patterns)
		if err != nil {
			fmt.Printf("Error searching images: %v\n", err)
			os.Exit(1)
		}

		output = results
		fmt.Printf("\nFound %d matching images:\n", len(results))
		for _, result := range results {
			fmt.Printf("\nImage: %s\n", result.Name)
			fmt.Printf("Version: %s\n", result.Version)
			fmt.Printf("SHA256: %s\n", result.SHA256)
		}
	} else {
		// Get filtered results
		results, err := client.SearchAndFilterImages(patterns)
		if err != nil {
			fmt.Printf("Error searching and filtering images: %v\n", err)
			os.Exit(1)
		}

		output = results
		fmt.Printf("\nFound %d matching images:\n", len(results))
		for name, tags := range results {
			fmt.Printf("\nImage: %s\n", name)
			fmt.Printf("Tags: %s\n", strings.Join(tags, ", "))
		}
	}

	// Save to file if specified
	if *outputFile != "" {
		// Convert output to JSON
		jsonData, err := json.MarshalIndent(output, "", "  ")
		if err != nil {
			fmt.Printf("Error encoding results to JSON: %v\n", err)
			os.Exit(1)
		}

		// Ensure the file ends with a newline
		jsonData = append(jsonData, '\n')

		// Get absolute path for better error reporting
		absPath, err := filepath.Abs(*outputFile)
		if err != nil {
			fmt.Printf("Error resolving output file path: %v\n", err)
			os.Exit(1)
		}

		// Create the directory if it doesn't exist
		dir := filepath.Dir(absPath)
		if err := os.MkdirAll(dir, 0755); err != nil {
			fmt.Printf("Error creating directory %s: %v\n", dir, err)
			os.Exit(1)
		}

		// Write the file
		if err := os.WriteFile(absPath, jsonData, 0644); err != nil {
			fmt.Printf("Error writing to file %s: %v\n", absPath, err)
			os.Exit(1)
		}

		fmt.Printf("\nResults saved to %s\n", absPath)
		
		// Verify the file was created
		if _, err := os.Stat(absPath); err != nil {
			fmt.Printf("Error: Failed to verify file creation at %s: %v\n", absPath, err)
			os.Exit(1)
		}
	}
} 