import os
import re
import argparse
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

class PDFPagesToAssistant:
    
    def __init__(self, overwrite: bool):

        # Load environment variables from .env file
        load_dotenv()

        # Get variables from environment
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        self.OUTPUT_DIR = Path(os.getenv('OUTPUT_DIR', 'Docs'))
        self.overwrite = overwrite

        # Check for missing variables
        if not self.OPENAI_API_KEY:
            raise ValueError("API key not found. Please set the OPENAI_API_KEY environment variable.")

        # Initialize OpenAI client with the API key from environment variable
        self.client = OpenAI(api_key=self.OPENAI_API_KEY)

        # Define the name for the vector store
        self.vector_store_name = f"Test APE"

        # Define the name of the assistant
        self.assistant_name = f"Acolad Assistant APE Test"

    def upload_pages_to_vectorstorage(self):
        # List all vector stores to check if one with the same name already exists
        existing_vector_stores = self.client.beta.vector_stores.list()
        vector_store_id = None

        for vector_store_data in existing_vector_stores.data:
            if vector_store_data.name == self.vector_store_name:
                vector_store_id = vector_store_data.id
                break

        # If a vector store with the same name exists and overwrite is set, delete it
        if vector_store_id:
            if self.overwrite:
                print(f"Vector store with name '{self.vector_store_name}' already exists. Deleting it...")
                self.client.beta.vector_stores.delete(vector_store_id)
                print(f"Deleted vector store with ID {vector_store_id}")
            else:
                print(f"Vector store with name '{self.vector_store_name}' already exists. Use --overwrite to delete it.")
                return

        # Create a new vector store
        self.vector_store = self.client.beta.vector_stores.create(name=self.vector_store_name)

        # Get list of PDF files in output_dir directory
        file_paths = [path for path in self.OUTPUT_DIR.iterdir() if path.suffix == ".pdf"]
        file_streams = []

        # Try to open each file and handle any errors
        for path in file_paths:
            try:
                filename = path.name
                # Extract filename without date and time part
                # base_filename = re.match(r'(.+?)_\d{8}_\d{6}\.pdf', filename).group(1)
                
                # Check if the file already exists in OpenAI storage
                existing_files = self.client.files.list()
                for f in existing_files.data:
                    if filename in f.filename:
                        print(f"File with base name '{filename}' already exists. Deleting it...")
                        self.client.files.delete(f.id)
                        print(f"Deleted file with ID {f.id}")
                
                # If no matching file is found or after deletion, open the new file for upload
                file_streams.append(path.open("rb"))
            except Exception as e:
                print(f"Error opening file {path}: {e}")

        # Upload and poll the files, and add them to the vector store
        if file_streams:
            file_batch = self.client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=self.vector_store.id, files=file_streams
            )

            # Check the status
            print(f"File batch status: {file_batch.status}")
            print(f"File counts: {file_batch.file_counts}")
        else:
            print("No files were successfully opened and uploaded.")

        # Close the file streams after processing
        for stream in file_streams:
            try:
                stream.close()
            except Exception as e:
                print(f"Error closing file stream: {e}")

    def update_assistant(self):
        # Fetch an existing Assistant (assuming you have the assistant ID)
        assistants = self.client.beta.assistants.list()
        assistant_id = None

        for assistant_data in assistants.data:
            if assistant_data.name == self.assistant_name:
                assistant_id = assistant_data.id
                break

        if assistant_id:
            # Update the Assistant to Use the New Vector Store
            assistant = self.client.beta.assistants.update(
                assistant_id=assistant_id,
                tool_resources={"file_search": {"vector_store_ids": [self.vector_store.id]}},
            )
            print(f"Updated assistant '{assistant.name}' with new vector store.")
        else:
            # Create a new Assistant if it doesn't exist
            assistant = self.client.beta.assistants.create(
                name=self.assistant_name,
                instructions="You are a helpful assistant that performs automated post-editing based on the provided files. Your primary goal is to enhance clarity, precision, and flow in the text while doing a post editing based on the provided files. If translation is requested, first perform the automated post-editing on the original text based on the provided files, then translate the edited text into the specified language (e.g., Text. (language)). Do not rely on prior knowledge or external information, focus solely on improving the provided content. Ensure the post-edited and translated version reflect these improvements.",
                model="gpt-4o-mini",
                tools=[{"type": "file_search"}],
            )

            # Update the Assistant to Use the New Vector Store
            assistant = self.client.beta.assistants.update(
                assistant_id=assistant.id,
                tool_resources={"file_search": {"vector_store_ids": [self.vector_store.id]}},
            )
            print(f"Created and updated assistant '{assistant.name}' with new vector store.")

def main():

    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Export files to VS using the Confluence API.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing vector store if it exists")
    args = parser.parse_args()

    # Instantiate the PDFPagesToAssistant class with the overwrite argument
    confluence_assistant = PDFPagesToAssistant(overwrite=args.overwrite)

    # Upload pages to vector storage
    confluence_assistant.upload_pages_to_vectorstorage()

    # Update assistant with the vector store
    confluence_assistant.update_assistant()

if __name__ == "__main__":
    main()
