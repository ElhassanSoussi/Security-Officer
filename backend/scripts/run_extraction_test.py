import sys
import os
# Adjust path to include backend root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.excel_agent import excel_agent
from openpyxl import load_workbook

def run_test():
    print("🚀 Running End-to-End Extraction Test (Real AI Mode)...")
    
    input_path = "test_questionnaire.xlsx"
    output_path = "test_questionnaire_FILLED.xlsx"
    org_id = "acme-corp"
    
    if not os.path.exists(input_path):
        print(f"❌ Input file not found: {input_path}")
        return

    # Read file content
    with open(input_path, "rb") as f:
        content = f.read()

    print("🧠 Analyzing Excel...")
    try:
        results = excel_agent.analyze_excel(content, org_id, None)
    except Exception as e:
        print(f"❌ Analysis Failed: {e}")
        # If vector store is missing config or deps, it might fail here.
        return

    print("\n----- EXTRACTED ANSWERS -----")
    for item in results:
        print(f"Q: {item.question}")
        print(f"A: {item.ai_answer}")
        print(f"Confidence: {item.confidence}")
        print(f"Sources: {item.sources}")
        print("-" * 30)

    print("\n💾 Generating Final Excel...")
    filled_content = excel_agent.generate_excel(content, results)
    
    with open(output_path, "wb") as f:
        f.write(filled_content)
        
    print(f"✅ Saved filled Excel to: {output_path}")

if __name__ == "__main__":
    run_test()
