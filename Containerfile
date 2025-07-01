# Containerfile
FROM ubuntu:24.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH=/app/.venv/bin:$PATH

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # System essentials
    ca-certificates \
    procps \
    net-tools \
    dnsutils \
    iproute2 \
    lsof \
    # Python environment
    python3.12 \
    python3.12-dev \
    python3.12-venv \
    python3-pip \
    # Development tools
    build-essential \
    golang \
    nodejs \
    npm \
    # Version control
    git \
    tig \
    # Security & containerization
    firejail \
    apparmor \
    # Text editors
    vim \
    nano \
    neovim \
    # System monitoring & analysis
    htop \
    glances \
    neofetch \
    iotop \
    sysstat \
    strace \
    ltrace \
    # Network utilities
    curl \
    wget \
    nmap \
    traceroute \
    mtr \
    openssh-client \
    socat \
    netcat-openbsd \
    httpie \
    iperf3 \
    tshark \
    # Browsers and web tools
    chromium-browser \
    chromium-driver \
    # File management
    tree \
    rsync \
    ncdu \
    ranger \
    # Compression utilities
    tar \
    gzip \
    pigz \
    bzip2 \
    xz-utils \
    p7zip-full \
    rar \
    unrar \
    zstd \
    lzip \
    lzma \
    cpio \
    unzip \
    zip \
    # Data formats & processing
    jq \
    yq \
    # Search tools
    fd-find \
    ripgrep \
    silversearcher-ag \
    # Shell & terminal utilities
    tmux \
    byobu \
    fzf \
    zsh \
    watch \
    entr \
    moreutils \
    parallel \
    pv \
    less \
    bc \
    bat \
    ncurses-bin \
    # Media processing
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libavfilter-dev \
    imagemagick \
    libmagickwand-dev \
    # Security and penetration testing tools
    nmap \
    nikto \
    sqlmap \
    dirb \
    gobuster \
    aircrack-ng \
    hydra \
    hashcat \
    john \
    # Encryption utilities
    gnupg \
    openssl \
    cryptsetup \
    age \
    keychain \
    libssl-dev \
    libffi-dev \
    # Database clients
    postgresql-client \
    mysql-client \
    redis-tools \
    sqlite3 \
    # Infrastructure as code tools
    ansible \
    hugo \
    # Document processing & language tools
    pandoc \
    tesseract-ocr \
    tesseract-ocr-eng \
    hunspell \
    translate-shell \
    poppler-utils \
    wkhtmltopdf \
    figlet \
    wordnet \
    aspell \
    aspell-en \
    libxml2-dev \
    libxslt1-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN GOBIN=/usr/local/bin go install github.com/eliukblau/pixterm/cmd/pixterm@latest

# Setup Python virtual environment using uv
RUN python3.12 -m venv /app/.venv
RUN /app/.venv/bin/pip install --upgrade pip setuptools wheel
RUN /app/.venv/bin/pip install uv

# Copy pyproject.toml for installation
COPY pyproject.toml /app/

# Install MCP Python SDK and other dependencies directly from pyproject.toml
WORKDIR /app
RUN /app/.venv/bin/uv pip install --no-cache-dir -e .

# Set appropriate permissions for the ubuntu user
RUN chown -R ubuntu:ubuntu /app

# Copy application code and project files
COPY --chown=ubuntu:ubuntu ./cmcp /app/cmcp
COPY --chown=ubuntu:ubuntu README.md /app/

# Copy AppArmor profiles (but don't load them during build)
COPY apparmor/mcp-bash /etc/apparmor.d/
COPY apparmor/mcp-python /etc/apparmor.d/

# Copy startup script
COPY --chown=ubuntu:ubuntu scripts/startup.sh /app/startup.sh

# Set working directory
WORKDIR /app

# Switch to ubuntu user
USER ubuntu

# Expose API port
EXPOSE 8000

# Start the application using our startup script
CMD ["/app/startup.sh"] 