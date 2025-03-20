# Container-MCP Scripts

This directory contains utility scripts for the Container-MCP project. These scripts help with setting up the development environment, building and running the container, and running tests.

## Available Scripts

### 00-all-in-one.sh

A convenience script that runs all steps in sequence to set up the Container-MCP project. This includes:
1. Initializing the project environment
2. Building the container
3. Setting up the environment for the container
4. Running the container
5. Running tests

Usage:
```bash
bin/00-all-in-one.sh
```

### 01-init.sh

Initializes the Container-MCP project by:
- Creating necessary directories
- Setting up a default configuration
- Creating and activating a Python virtual environment
- Installing required dependencies
- Checking for required system packages
- Checking for container tools (Podman/Docker)

Usage:
```bash
bin/01-init.sh
```

### 02-build-container.sh

Builds the container image for Container-MCP using Podman or Docker.

Usage:
```bash
bin/02-build-container.sh
```

### 03-setup-environment.sh

Sets up the environment for running the Container-MCP container, including:
- Creating necessary directories with appropriate permissions
- Checking for SELinux status and setting appropriate context
- Creating a container network
- Copying default configuration files
- Installing required host system packages

Usage:
```bash
bin/03-setup-environment.sh
```

### 04-run-container.sh

Runs the Container-MCP container using either Docker Compose or a direct container run command.

Usage:
```bash
bin/04-run-container.sh
```

### 05-run-tests.sh

Runs tests for the Container-MCP project, with options for running unit tests, integration tests, or all tests, and optionally generating coverage reports.

Usage:
```bash
bin/05-run-tests.sh [unit|integration|all]
```

## General Usage

For a first-time setup, you can either run the all-in-one script:

```bash
bin/00-all-in-one.sh
```

Or run the scripts individually in sequence:

```bash
bin/01-init.sh
bin/02-build-container.sh
bin/03-setup-environment.sh
bin/04-run-container.sh
bin/05-run-tests.sh
```

## Requirements

- Python 3.6+
- Docker or Podman
- firejail (for sandbox functionality)
- apparmor and apparmor-utils (for enhanced security) 