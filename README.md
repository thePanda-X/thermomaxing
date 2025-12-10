# Thermomaxing 🥘🤖

**Thermomaxing** is an intelligent recipe importer for the [Cookidoo](https://cookidoo.thermomix.com/) app. It allows you to take any recipe URL from the web and automatically import it into your Cookidoo account using AI-powered data extraction.

## ✨ Features

- **AI-Powered Extraction**: Uses a local LLM (via Ollama) to intelligently parse ingredients, steps, and metadata from any recipe website.
- **Automated Import**: Automatically logs into your Cookidoo account and creates the recipe for you.
- **Real-time Progress**: Watch the import process step-by-step via a clean, modern web interface.
- **Universal Compatibility**: Works with virtually any recipe site, not just supported ones.

## 🚀 Getting Started

### Prerequisites

- **Python 3.8+**
- **[Ollama](https://ollama.com/)**: You need to have Ollama installed and running locally.
- **Cookidoo Account**: A valid subscription is required to create recipes.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/thePanda-X/thermomaxing.git
    cd thermomaxing
    ```

2.  **Set up a virtual environment (optional but recommended):**
    ```bash
    # Windows (PowerShell)
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    
    # Linux/macOS
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    playwright install
    ```
    or give the auto setup a go if you're on windows.
    ```bash
    ./setup_venv.ps1
    ```

4.  **Set up Ollama:**
    Make sure Ollama is running and pull the default model (or whichever one you plan to use):
    ```bash
    ollama pull qwen3:4b-instruct # or your favourite model!
    ```

5.  **Configuration:**
    Create a `.env` file in the root directory with your Cookidoo credentials and model preference:
    ```env
    COOKIDOO_USERNAME=your_email@example.com
    COOKIDOO_PASSWORD=your_password
    OLLAMA_MODEL=qwen3:4b-instruct
    ```

### Usage

1.  **Start the server:**
    ```bash
    python server.py
    ```

2.  **Open the Web Interface:**
    Navigate to `http://localhost:8000` in your browser.

3.  **Import a Recipe:**
    - Paste a URL of a recipe you want to cook.
    - Click **Import**.
    - Watch as the AI extracts the details and adds it to your Cookidoo account!

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI
- **AI/LLM**: Ollama (running locally)
- **Browser Automation**: Playwright
- **Frontend**: HTML5, CSS3, Vanilla JavaScript

## ⚠️ Disclaimer

This tool is for educational purposes and personal use. It automates user interactions with the Cookidoo platform. Use responsibly and ensure you comply with the terms of service of the websites you are scraping.
