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
    ca-certificates \
    curl \
    wget \
    git \
    python3.12 \
    python3.12-dev \
    python3.12-venv \
    python3-pip \
    firejail \
    apparmor \
    chromium-browser \
    chromium-driver \
    jq \
    yq \
    vim \
    nano \
    tree \
    htop \
    net-tools \
    dnsutils \
    procps \
    lsof \
    rsync \
    unzip \
    zip \
    ncdu \
    fd-find \
    ripgrep \
    bc \
    bat \
    tar \
    gzip \
    bzip2 \
    xz-utils \
    p7zip-full \
    rar \
    unrar \
    zstd \
    lzip \
    lzma \
    cpio \
    ffmpeg \
    build-essential \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libavfilter-dev \
    libssl-dev \
    libffi-dev \
    imagemagick \
    libmagickwand-dev \
    libxml2-dev \
    libxslt1-dev \
    tmux \
    fzf \
    moreutils \
    parallel \
    pv \
    ranger \
    silversearcher-ag \
    openssh-client \
    tig \
    nmap \
    iproute2 \
    traceroute \
    mtr \
    pigz \
    less \
    byobu \
    watch \
    glances \
    neofetch \
    neovim \
    sqlite3 \
    redis-tools \
    zsh \
    strace \
    ltrace \
    sysstat \
    iotop \
    socat \
    netcat-openbsd \
    httpie \
    iperf3 \
    entr \
    ncurses-bin \
    golang \
    nodejs \
    npm \
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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

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