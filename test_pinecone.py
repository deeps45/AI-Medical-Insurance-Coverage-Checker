#!/usr/bin/env python3
import os
import pinecone
from dotenv import load_dotenv

# Load environment variables
load_dotenv('backend/.env')

print("Testing Pinecone connection...")
print(f"API Key (first 10 chars): {os.getenv('PINECONE_API_KEY', 'NOT_SET')[:10]}...")
print(f"Environment: {os.getenv('PINECONE_ENVIRONMENT', 'NOT_SET')}")
print(f"Index Name: {os.getenv('PINECONE_INDEX_NAME', 'NOT_SET')}")

try:
    # Initialize Pinecone
    pinecone.init(
        api_key=os.getenv("PINECONE_API_KEY"),
        environment=os.getenv("PINECONE_ENVIRONMENT", "gcp-starter")
    )
    print("✅ Pinecone initialized successfully!")
    
    # List indexes
    indexes = pinecone.list_indexes()
    print(f"Available indexes: {indexes}")
    
    # Check if our index exists
    index_name = os.getenv("PINECONE_INDEX_NAME", "docsage-lite")
    if index_name in indexes:
        print(f"✅ Index '{index_name}' exists!")
    else:
        print(f"❌ Index '{index_name}' does not exist. Creating it...")
        try:
            pinecone.create_index(
                name=index_name,
                dimension=1536,
                metric="cosine"
            )
            print(f"✅ Index '{index_name}' created successfully!")
        except Exception as e:
            print(f"❌ Failed to create index: {e}")
            
except Exception as e:
    print(f"❌ Pinecone connection failed: {e}")
    print(f"Error type: {type(e)}")
