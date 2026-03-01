import os
import sys
import asyncio

# Ensure we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.core.ingestion import pdf_processor

# Mock Content for NYC Regulations
SCA_SAFETY_TEXT = """
NYC SCHOOL CONSTRUCTION AUTHORITY - SAFETY PROGRAM & PROCEDURES MANUAL (2026 EDITION)

SECTION 1: FALL PROTECTION
1.1 General Requirements
All contractors must provide fall protection for employees working at heights of 6 feet or more.
Acceptable systems include guardrails, safety nets, or personal fall arrest systems.
Harnesses must be inspected daily before use.
Documentation of inspection must be available on-site for the Site Safety Manager.

SECTION 2: SCAFFOLDING
2.1 Supported Scaffolds
All supported scaffolds must be erected under the supervision of a competent person.
Base plates and mudsills are mandatory on all surfaces.
Scaffold tags (Green, Yellow, Red) must be updated daily.

SECTION 3: SILICA DUST CONTROL
3.1 Engineering Controls
Contractors must use water delivery systems or dust collection vacuums for all cutting of masonry or concrete.
Dry cutting is strictly prohibited on SCA projects.
"""

MTA_VENDOR_RESP_TEXT = """
METROPOLITAN TRANSPORTATION AUTHORITY - VENDOR RESPONSIBILITY QUESTIONNAIRE

SECTION A: GENERAL INFORMATION
A1. Principal Owner
The Vendor must disclose all owners with >10% equity.
failure to disclose ownership will result in immediate disqualification.

SECTION B: INTEGRITY & ETHICS
B1. Criminal History
Has the vendor or any principal been convicted of a crime in the last 5 years?
If YES, attach detailed explanation in Schedule F.

B2. Debarment
Has the vendor been debarred by any NYC, NYS, or Federal agency in the last 3 years?
A "Yes" answer requires a full explanation and may lead to a non-responsibility finding.
"""

PASSPORT_GUIDE_TEXT = """
NYC PASSPORT - VENDOR ENROLLMENT GUIDE (2025-2026)

1. ACCOUNT CREATION
Vendors must create an NYC.ID account to access PASSPort.
The primary contact should be an officer of the company.

2. COMMODITY CODES
Select all NIGP codes that apply to your business. 
Incorrect codes may limit bid notifications.

3. DISCLOSURES
All annual gross revenue must be reported for the last 3 fiscal years.
Subcontractors receiving >$100k must also be disclosed in the system.
"""

async def seed_global_docs():
    print("🚀 Starting Global Library Seeding...")
    
    docs = [
        ("SCA_Safety_Manual_2026.txt", SCA_SAFETY_TEXT),
        ("MTA_Vendor_Responsibility.txt", MTA_VENDOR_RESP_TEXT),
        ("NYC_PASSPort_Guide.txt", PASSPORT_GUIDE_TEXT)
    ]
    
    for filename, content in docs:
        # Write generic text file
        with open(filename, "w") as f:
            f.write(content)
        
        # Read as bytes
        with open(filename, "rb") as f:
            file_bps = f.read()
            
        print(f"📥 Ingesting {filename} into NYC_GLOBAL scope...")
        try:
            # We use a special org_id for global docs, e.g., "NYC_GOV"
            result = pdf_processor.process_and_store_document(
                file_content=file_bps,
                filename=filename,
                org_id="NYC_GOV",
                project_id=None,
                scope="NYC_GLOBAL"
            )
            print(f"✅ Ingested {filename}: {result}")
        except Exception as e:
            print(f"❌ Failed to ingest {filename}: {e}")
            import traceback
            traceback.print_exc()
            
        # Cleanup
        if os.path.exists(filename):
            os.remove(filename)

if __name__ == "__main__":
    asyncio.run(seed_global_docs())
