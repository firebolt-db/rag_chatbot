import os
import sys
sys.path.append('/app')

print('=== Testing populate_table.py Script Execution ===')

try:
    from populate_table import generate_embeddings_and_populate_table
    from constants import LOCAL_GITHUB_PATH
    
    print(f'LOCAL_GITHUB_PATH: {LOCAL_GITHUB_PATH}')
    print(f'LOCAL_GITHUB_PATH exists: {os.path.exists(LOCAL_GITHUB_PATH)}')
    
    if os.path.exists(LOCAL_GITHUB_PATH):
        print('✅ populate_table.py can import successfully')
        print('✅ LOCAL_GITHUB_PATH is accessible from the script')
        
        rag_chatbot_path = os.path.join(LOCAL_GITHUB_PATH, 'rag_chatbot')
        if os.path.exists(rag_chatbot_path):
            print('✅ rag_chatbot repo accessible for document processing')
            
            files = []
            for root, dirs, filenames in os.walk(rag_chatbot_path):
                for filename in filenames:
                    if filename.endswith(('.md', '.txt', '.docx')):
                        files.append(os.path.join(root, filename))
            
            print(f'✅ Found {len(files)} processable documents in rag_chatbot repo')
            if files:
                print(f'   Sample files: {files[:3]}')
        else:
            print('❌ rag_chatbot repo not accessible')
    else:
        print('❌ LOCAL_GITHUB_PATH not accessible')
        
except Exception as e:
    print(f'❌ Error testing populate_table.py: {e}')
    import traceback
    traceback.print_exc()

print('\n=== Test Complete ===')
