import os
import re
import argparse
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

class FilesToAssistant:
    
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
        self.assistant_name = f"RAG for APE"

    def convert_xlsx_to_txt(self, xlsx_path):
        try:
            # Load the Excel file
            xls = pd.ExcelFile(xlsx_path)
            txt_files = []

            # Iterate over each sheet and save as a separate TXT file
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)

                # Define the TXT path for each sheet
                txt_path = xlsx_path.with_name(f"{xlsx_path.stem}_{sheet_name}.txt")
                
                # Save the sheet content as TXT
                df.to_csv(txt_path, sep='\t', index=False)
                print(f"Converted {xlsx_path} - Sheet '{sheet_name}' to {txt_path}")

                txt_files.append(txt_path)

            return txt_files
        
        except Exception as e:
            print(f"Error converting {xlsx_path} to TXT: {e}")
            return []

    def process_files(self):
        # Get list of all files in output_dir directory
        file_paths = [path for path in self.OUTPUT_DIR.iterdir() if path.is_file()]
        txt_files = []
        non_xlsx_files = []

        # Convert .xlsx files to .txt and collect other files
        for path in file_paths:
            if path.suffix == '.xlsx':
                txt_files.extend(self.convert_xlsx_to_txt(path))
            else:
                non_xlsx_files.append(path)

        # Combine txt files and non-xlsx files for upload
        all_files_to_upload = txt_files + non_xlsx_files
        return all_files_to_upload, txt_files

    def upload_files_to_vectorstorage(self):
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

        # Process files (conversion + deletion) and get the list of files to upload
        files_to_upload, txt_files = self.process_files()
        file_streams = []

        # Try to open each file and handle any errors
        for path in files_to_upload:
            try:
                filename = path.name

                # Check if the file already exists in OpenAI storage
                existing_files = self.client.files.list()
                for f in existing_files.data:
                    if filename in f.filename:
                        print(f"File with base name '{filename}' already exists. Deleting it...")
                        self.client.files.delete(f.id)
                        print(f"Deleted file with ID {f.id}")

                # Open the file for upload, excluding .xlsx files
                if path.suffix != '.xlsx':
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

        # Delete the .txt files created during the conversion
        for txt_file in txt_files:
            try:
                txt_file.unlink()
                print(f"Deleted the temporary TXT file: {txt_file}")
            except Exception as e:
                print(f"Error deleting TXT file {txt_file}: {e}")

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
                instructions="You are a helpful assistant specializing in automated post-editing based on the provided translation files. Your primary objective is to enhance the clarity, precision, and flow of the text during the post-editing process. All edits should be made as accurately as possible, strictly according to the provided translation files. If translation is also required, first perform the automated post-editing on the original text using the provided files, then translate the edited text into the specified language (e.g., Text. (language)). Do not rely on prior knowledge or external information—focus exclusively on refining the provided content. Ensure that both the post-edited and translated versions reflect these improvements.",
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
    parser = argparse.ArgumentParser(description="Export files to VS.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing vector store if it exists")
    args = parser.parse_args()

    # Instantiate the FilesToAssistant class with the overwrite argument
    confluence_assistant = FilesToAssistant(overwrite=args.overwrite)

    # Upload files to vector storage
    confluence_assistant.upload_files_to_vectorstorage()

    # Update assistant with the vector store
    confluence_assistant.update_assistant()

if __name__ == "__main__":
    main()
