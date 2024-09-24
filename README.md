# Test APE (Automatic Post-Editing)

## Setup

1. **Clone the Repository:**
    ```bash
    git clone https://github.com/APE_TEST.git
    cd APE_TEST
    ```

2. **Configure Environment Variables:**

    Fill the `.env` file in the root directory with your Confluence parameters along with the OpenAI API key. 

    ```plaintext
    OPENAI_API_KEY=your_api_key
    OUTPUT_DIR=Docs
    ```

3. **Install Dependencies using python-poetry:**
    ```bash
    # Install Poetry (if not already installed)
    curl -sSL https://install.python-poetry.org | python3 -

    # Install dependencies
    poetry install
    ```

## Usage

### 1. Export translation Files to OpenAI VectorStore

Use RAG for APE :

```bash
poetry run python ape_test.py --overwrite
```
### 2. You can now access the VectorStore from an assistant

```plaintext
https://platform.openai.com/assistants
```
