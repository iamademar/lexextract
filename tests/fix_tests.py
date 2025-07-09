#!/usr/bin/env python3

# Read the test file
with open('tests/test_upload.py', 'r') as f:
    content = f.read()

# Replace the POST calls that should succeed (add client_id=1)
replacements = [
    # test_upload_statement_success 
    ('response = client.post("/upload/statement", files=files)', 'response = client.post("/upload/statement?client_id=1", files=files)'),
    # test_upload_statement_file_saved
    ('response = client.post("/upload/statement", files=files)', 'response = client.post("/upload/statement?client_id=1", files=files)'),
    # test_upload_statement_invalid_mime_type
    ('response = client.post("/upload/statement", files=files)', 'response = client.post("/upload/statement?client_id=1", files=files)'),
    # test_upload_statement_large_file
    ('response = client.post("/upload/statement", files=files)', 'response = client.post("/upload/statement?client_id=1", files=files)'),
    # test_upload_statement_no_file
    ('response = client.post("/upload/statement")', 'response = client.post("/upload/statement?client_id=1")'),
    # test_upload_creates_directory
    ('response = client.post("/upload/statement", files=files)', 'response = client.post("/upload/statement?client_id=1", files=files)'),
]

# Apply replacements one by one to handle duplicates correctly
for old, new in replacements:
    content = content.replace(old, new, 1)

# Add client_id verification to test_upload_statement_file_saved
content = content.replace(
    'assert statement.file_path is not None',
    'assert statement.file_path is not None\n        assert statement.client_id == 1  # Verify client_id is set correctly'
)

# Add new test functions for missing and invalid client_id
new_tests = '''

def test_upload_statement_missing_client_id():
    """Test upload without providing client_id"""
    pdf_content = create_dummy_pdf()
    files = {
        "file": ("test_statement.pdf", io.BytesIO(pdf_content), "application/pdf")
    }
    
    response = client.post("/upload/statement", files=files)
    
    assert response.status_code == 422  # Validation error

def test_upload_statement_invalid_client_id():
    """Test upload with non-existent client_id"""
    pdf_content = create_dummy_pdf()
    files = {
        "file": ("test_statement.pdf", io.BytesIO(pdf_content), "application/pdf")
    }
    
    response = client.post("/upload/statement?client_id=999", files=files)
    
    assert response.status_code == 404
    assert "Client with ID 999 not found" in response.json()["detail"]
'''

# Add the new tests before the end of the file
content = content.rstrip() + new_tests

# Write the updated content
with open('tests/test_upload.py', 'w') as f:
    f.write(content)

print("Test file updated successfully!")
