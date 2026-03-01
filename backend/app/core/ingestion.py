import io
import json
from typing import List, Dict, Any, Optional
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    class RecursiveCharacterTextSplitter:
        def __init__(self, **kwargs): pass
        def split_text(self, text): return [text]
try:
    from openai import OpenAI
except ImportError:
    class OpenAI:
        def __init__(self, api_key=None): self.embeddings = self
        def create(self, **kwargs): return type("obj", (), {"data": [type("obj", (), {"embedding": []})]})()
from app.core.config import get_settings
from app.core.database import get_supabase

settings = get_settings()

class PDFProcessor:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            is_separator_regex=False,
        )
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def extract_and_chunk(self, file_content: bytes, filename: str) -> List[Dict[str, Any]]:
        chunks = []
        
        if filename.endswith(".pdf"):
            import io
            from pypdf import PdfReader
            pdf_reader = PdfReader(io.BytesIO(file_content))
            
            for page_num, page in enumerate(pdf_reader.pages, start=1):
                text = page.extract_text()
                if not text:
                    continue
                    
                page_chunks = self.text_splitter.split_text(text)
                
                for i, chunk_text in enumerate(page_chunks):
                    chunks.append({
                        "page_number": page_num,
                        "chunk_index": i,
                        "content": chunk_text
                    })
                    
        elif filename.endswith(".txt"):
            text = file_content.decode("utf-8")
            page_chunks = self.text_splitter.split_text(text)
            for i, chunk_text in enumerate(page_chunks):
                chunks.append({
                    "page_number": 1, # Text files treated as single page
                    "chunk_index": i,
                    "content": chunk_text
                })
                
        elif filename.endswith(".docx"):
            import io
            from docx import Document
            doc = Document(io.BytesIO(file_content))
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            text = "\n".join(full_text)
            
            page_chunks = self.text_splitter.split_text(text)
            for i, chunk_text in enumerate(page_chunks):
                chunks.append({
                    "page_number": 1, # DOCX treated as single scrolling doc for now
                    "chunk_index": i,
                    "content": chunk_text
                })

        return chunks

    def get_embedding(self, text: str) -> List[float]:
        text = text.replace("\n", " ")
        return self.openai_client.embeddings.create(input=[text], model=settings.embedding_model).data[0].embedding

    def process_and_store_document(
        self,
        file_content: bytes,
        filename: str,
        org_id: str,
        project_id: Optional[str],
        scope: str,
        token: Optional[str] = None,
    ):
        # Prefer RLS-scoped client using the caller JWT. This keeps tenancy rules
        # consistent and avoids requiring service_role for local dev.
        sb = get_supabase(token) if token else get_supabase(None)
        
        # 1. Create Document Record
        doc_data = {
            "org_id": org_id,
            "project_id": project_id,
            "scope": scope,
            "filename": filename,
            "metadata": {"page_count": 0} # Update later
        }
        res = sb.table("documents").insert(doc_data).execute()
        document_id = res.data[0]['id']

        # 2. Extract & Chunk
        chunks_data = self.extract_and_chunk(file_content, filename)
        
        # 3. Embed & Store Chunks
        db_rows = []
        for chunk in chunks_data:
            embedding = self.get_embedding(chunk["content"])
            db_rows.append({
                "document_id": document_id,
                "page_number": chunk["page_number"],
                "chunk_index": chunk["chunk_index"],
                "content": chunk["content"],
                "embedding": embedding
            })
            
            # Batch insert every 50 to avoid payload limits
            if len(db_rows) >= 50:
                sb.table("chunks").insert(db_rows).execute()
                db_rows = []
        
        if db_rows:
            sb.table("chunks").insert(db_rows).execute()

        # Update metadata if needed
        # self.supabase.table("documents").update(...).eq("id", document_id).execute()
        
        return {"document_id": document_id, "chunks_count": len(chunks_data)}

pdf_processor = PDFProcessor()
