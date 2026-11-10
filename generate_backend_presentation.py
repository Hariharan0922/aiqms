import sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

def create_deck(filename="AiDocMaker_Backend_Architecture_Presentation.pptx"):
    prs = Presentation()
    # 16:9 Widescreen slides (13.333 x 7.5 inches)
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Palette
    C_BG_DARK = RGBColor(15, 23, 42)       # Slate 900
    C_CARD_DARK = RGBColor(30, 41, 59)     # Slate 800
    C_CARD_BORDER = RGBColor(51, 65, 85)   # Slate 700
    C_ACCENT_BLUE = RGBColor(14, 165, 233) # Sky 500
    C_ACCENT_CYAN = RGBColor(56, 189, 248) # Sky 400
    C_ACCENT_GREEN = RGBColor(34, 197, 94) # Green 500
    C_ACCENT_AMBER = RGBColor(245, 158, 11)# Amber 500
    C_ACCENT_PURPLE = RGBColor(168, 85, 247)
    C_TEXT_WHITE = RGBColor(255, 255, 255)
    C_TEXT_MUTED = RGBColor(148, 163, 184) # Slate 400
    C_TEXT_BODY = RGBColor(226, 232, 240)  # Slate 200

    def add_header(slide, title, category="BACKEND ARCHITECTURE DEEP DIVE"):
        # Category pill
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(8), Inches(0.4))
        tf_cat = cat_box.text_frame
        tf_cat.word_wrap = True
        tf_cat.margin_left = tf_cat.margin_top = tf_cat.margin_right = tf_cat.margin_bottom = 0
        p_cat = tf_cat.paragraphs[0]
        p_cat.text = category.upper()
        p_cat.font.size = Pt(10)
        p_cat.font.bold = True
        p_cat.font.color.rgb = C_ACCENT_CYAN

        # Title
        t_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.7), Inches(11.5), Inches(0.8))
        tf = t_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(22)
        p.font.bold = True
        p.font.color.rgb = C_TEXT_WHITE

    def add_bg(slide):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        bg.fill.solid()
        bg.fill.fore_color.rgb = C_BG_DARK
        bg.line.fill.background()
        return bg

    def add_card(slide, left, top, width, height, title="", border_color=C_CARD_BORDER, bg_color=C_CARD_DARK):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        card.line.color.rgb = border_color
        card.line.width = Pt(1.2)
        
        if title:
            tb = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.15), width - Inches(0.4), Inches(0.4))
            tf = tb.text_frame
            tf.word_wrap = True
            tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
            p = tf.paragraphs[0]
            p.text = title
            p.font.size = Pt(13)
            p.font.bold = True
            p.font.color.rgb = C_ACCENT_CYAN
        return card

    # ==========================================
    # SLIDE 1: TITLE SLIDE
    # ==========================================
    s1 = prs.slides.add_slide(blank_layout)
    add_bg(s1)
    
    # Hero Title Box
    title_box = s1.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(11.3), Inches(3.5))
    tf1 = title_box.text_frame
    tf1.word_wrap = True
    
    p_tag = tf1.paragraphs[0]
    p_tag.text = "ENTERPRISE QUALITY MANAGEMENT & DOCUMENT AUTOMATION PLATFORM"
    p_tag.font.size = Pt(12)
    p_tag.font.bold = True
    p_tag.font.color.rgb = C_ACCENT_CYAN
    p_tag.space_after = Pt(14)
    
    p_main = tf1.add_paragraph()
    p_main.text = "AiDocMaker: Complete Backend Architecture"
    p_main.font.size = Pt(36)
    p_main.font.bold = True
    p_main.font.color.rgb = C_TEXT_WHITE
    p_main.space_after = Pt(14)
    
    p_sub = tf1.add_paragraph()
    p_sub.text = "Deterministic Regulatory Validation, High-Throughput NVIDIA NIM AI Microservices, and Native Document Generation for Regulated Life Sciences (ISO 13485:2016 / 21 CFR Part 820)"
    p_sub.font.size = Pt(15)
    p_sub.font.color.rgb = C_TEXT_MUTED
    
    # Metadata Footer Card
    meta_card = add_card(s1, Inches(1.0), Inches(5.4), Inches(11.33), Inches(1.3), "", C_CARD_BORDER)
    meta_box = s1.shapes.add_textbox(Inches(1.3), Inches(5.6), Inches(10.7), Inches(0.9))
    tf_meta = meta_box.text_frame
    tf_meta.word_wrap = True
    p_m1 = tf_meta.paragraphs[0]
    p_m1.text = "Core Tech Stack: FastAPI (Python 3.13) | NVIDIA NIM API | SQLAlchemy + SQLite/Postgres | ChromaDB | python-docx & ReportLab"
    p_m1.font.size = Pt(12)
    p_m1.font.bold = True
    p_m1.font.color.rgb = C_TEXT_WHITE
    p_m1.space_after = Pt(6)
    
    p_m2 = tf_meta.add_paragraph()
    p_m2.text = "Key Architectural Pillars: Zero-AI Deterministic Pre-Validation • Section-Level Regeneration • 6-State Governance State Machine • Segregation of Duties"
    p_m2.font.size = Pt(11)
    p_m2.font.color.rgb = C_ACCENT_BLUE

    s1.notes_slide.notes_text_frame.text = (
        "Welcome everyone. Today we are presenting the complete backend architecture of AiDocMaker (AIQMS).\n"
        "This platform is engineered specifically for regulated medical device and life sciences organizations "
        "complying with ISO 13485:2016, FDA 21 CFR Part 820, and GxP standards.\n"
        "Our backend uniquely marries deterministic rules-based quality gates with NVIDIA's enterprise NIM cloud inference, "
        "enforcing strict segregation of duties and producing authentic binary DOCX and PDF documents."
    )

    # ==========================================
    # SLIDE 2: EXECUTIVE SUMMARY & EVOLUTION
    # ==========================================
    s2 = prs.slides.add_slide(blank_layout)
    add_bg(s2)
    add_header(s2, "Executive Overview: Modernizing Regulated QMS Document Generation")
    
    c1 = add_card(s2, Inches(0.8), Inches(1.6), Inches(3.6), Inches(5.3), "The Regulatory Challenge")
    tb1 = s2.shapes.add_textbox(Inches(1.0), Inches(2.2), Inches(3.2), Inches(4.5))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    points1 = [
        ("Life Sciences Documentation Burden", "QMS documents (SOPs, CAPAs, Quality Manuals) require weeks of manual authoring and cross-referencing."),
        ("Strict Compliance Mandates", "ISO 13485:2016 & 21 CFR Part 820 require verifiable requirements traceability, review segregation, and tamper-proof audit trails."),
        ("Legacy AI Failure Modes", "Generic LLMs hallucinate clauses, violate required template structures, and fail compliance validation.")
    ]
    for h, b in points1:
        p = tf1.add_paragraph() if tf1.paragraphs[0].text else tf1.paragraphs[0]
        p.text = f"• {h}: "
        p.font.bold = True
        p.font.size = Pt(11)
        p.font.color.rgb = C_TEXT_WHITE
        p.space_after = Pt(2)
        p2 = tf1.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(10)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(10)

    c2 = add_card(s2, Inches(4.8), Inches(1.6), Inches(3.6), Inches(5.3), "Legacy Local Stack Bottlenecks")
    tb2 = s2.shapes.add_textbox(Inches(5.0), Inches(2.2), Inches(3.2), Inches(4.5))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    points2 = [
        ("Excessive Generation Latency", "Local 7B/13B models executed via in-process daemons consumed 35-70+ seconds per generation cycle."),
        ("Heavy Hardware Footprint", "Mandated local high-end GPUs (16GB+ VRAM), blocking scalable cloud deployments and developer onboarding."),
        ("Daemon Instability", "Local background inference processes suffered from random memory leaks, cold boot timeouts, and driver mismatches.")
    ]
    for h, b in points2:
        p = tf2.add_paragraph() if tf2.paragraphs[0].text else tf2.paragraphs[0]
        p.text = f"• {h}: "
        p.font.bold = True
        p.font.size = Pt(11)
        p.font.color.rgb = C_ACCENT_AMBER
        p.space_after = Pt(2)
        p2 = tf2.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(10)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(10)

    c3 = add_card(s2, Inches(8.8), Inches(1.6), Inches(3.7), Inches(5.3), "AiDocMaker NIM Architecture")
    tb3 = s2.shapes.add_textbox(Inches(9.0), Inches(2.2), Inches(3.3), Inches(4.5))
    tf3 = tb3.text_frame
    tf3.word_wrap = True
    points3 = [
        ("Sub-Second Cloud Inference", "Switched to hosted NVIDIA NIM API (poolside/laguna-xs-2.1 / Llama-3.1-70B) yielding ~0.8s round-trip response times."),
        ("Deterministic Pre-Validation", "100% of user inputs pass a deterministic rules engine before any external API invocation occurs."),
        ("Authentic Native Exports", "Pure Python DOCX & PDF generators with real XML/binary signatures, ISO headers, and sign-off blocks.")
    ]
    for h, b in points3:
        p = tf3.add_paragraph() if tf3.paragraphs[0].text else tf3.paragraphs[0]
        p.text = f"✓ {h}: "
        p.font.bold = True
        p.font.size = Pt(11)
        p.font.color.rgb = C_ACCENT_GREEN
        p.space_after = Pt(2)
        p2 = tf3.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(10)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(10)

    s2.notes_slide.notes_text_frame.text = (
        "Slide 2 establishes the core problem space and the architectural evolution of AiDocMaker.\n"
        "Previously, the system attempted to run heavy 7B-13B LLMs locally via Ollama daemons, "
        "which led to 35-70 second generation times, GPU memory errors, and deployment bottlenecks.\n"
        "We rearchitected the backend around two complementary pillars:\n"
        "1. Deterministic rules-based pre-validation that completely eliminates unnecessary AI calls and validates compliance data upfront.\n"
        "2. High-speed NVIDIA NIM hosted microservice inference, delivering high-quality, structured JSON documentation in under a second."
    )

    # ==========================================
    # SLIDE 3: HIGH-LEVEL ARCHITECTURE & PIPELINE
    # ==========================================
    s3 = prs.slides.add_slide(blank_layout)
    add_bg(s3)
    add_header(s3, "End-to-End System Architecture & Data Flow")
    
    # 6 Step Horizontal Pipeline Cards
    pipeline_steps = [
        ("1. Input & Form", "FastAPI receives dynamic field values & regulatory applicability answers.", C_ACCENT_BLUE),
        ("2. Rules Engine", "Zero-AI validation checks required fields, formats & ISO criteria.", C_ACCENT_AMBER),
        ("3. Prompt Service", "Constructs schema-enforced prompt with ISO standards & context.", C_ACCENT_PURPLE),
        ("4. NVIDIA NIM", "Hosted inference executes OpenAI-compatible JSON generation.", C_ACCENT_CYAN),
        ("5. Template Mapper", "Validates Pydantic schema, preserves ordering, enables atomic edits.", C_ACCENT_GREEN),
        ("6. Document Store", "Commits revision to SQLite/Postgres with SHA-256 & renders exports.", C_ACCENT_BLUE)
    ]
    
    card_w = Inches(1.8)
    card_h = Inches(2.2)
    start_x = Inches(0.8)
    gap = Inches(0.18)
    
    for i, (stitle, sdesc, col) in enumerate(pipeline_steps):
        x = start_x + i * (card_w + gap)
        c = add_card(s3, x, Inches(1.6), card_w, card_h, "", col)
        
        tb = s3.shapes.add_textbox(x + Inches(0.1), Inches(1.7), card_w - Inches(0.2), card_h - Inches(0.2))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        
        p1 = tf.paragraphs[0]
        p1.text = stitle
        p1.font.size = Pt(11)
        p1.font.bold = True
        p1.font.color.rgb = col
        p1.space_after = Pt(6)
        
        p2 = tf.add_paragraph()
        p2.text = sdesc
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = C_TEXT_BODY

    # Lower Architectural Subsystems Details
    sub_w = Inches(5.7)
    sub_h = Inches(2.9)
    
    c_left = add_card(s3, Inches(0.8), Inches(4.1), sub_w, sub_h, "Core Synchronous Processing Subsystems")
    tb_l = s3.shapes.add_textbox(Inches(1.0), Inches(4.6), sub_w - Inches(0.4), sub_h - Inches(0.6))
    tf_l = tb_l.text_frame
    tf_l.word_wrap = True
    l_points = [
        ("Validation Gate (FastAPI)", "Guarantees no invalid request reaches the external LLM; returns structured 400/422 with exact field path findings."),
        ("NvidiaService Client", "Configured with httpx connection pooling, timeout handling (120s default), and bounded exponential retries (2 attempts)."),
        ("Structured JSON Parsing", "Robust parser with regex fallback extracting JSON blocks even when models output markdown fences or reasoning traces.")
    ]
    for h, b in l_points:
        p = tf_l.add_paragraph() if tf_l.paragraphs[0].text else tf_l.paragraphs[0]
        p.text = f"• {h}: "
        p.font.bold = True
        p.font.size = Pt(10)
        p.font.color.rgb = C_TEXT_WHITE
        p_body = tf_l.add_paragraph()
        p_body.text = f"  {b}"
        p_body.font.size = Pt(9.5)
        p_body.font.color.rgb = C_TEXT_MUTED
        p_body.space_after = Pt(4)

    c_right = add_card(s3, Inches(6.8), Inches(4.1), sub_w, sub_h, "Asynchronous & Supporting Subsystems")
    tb_r = s3.shapes.add_textbox(Inches(7.0), Inches(4.6), sub_w - Inches(0.4), sub_h - Inches(0.6))
    tf_r = tb_r.text_frame
    tf_r.word_wrap = True
    r_points = [
        ("Vector Search & RAG (ChromaDB)", "Ingests ISO standards and organizational guidelines into partitioned vector collections for context enhancement."),
        ("Document Ingestion Engine", "Extracts structured sections from uploaded DOCX/PDF reference documents for automatic knowledge assimilation."),
        ("Audit & Traceability Subsystem", "Tamper-evident audit logging and bidirectional linking between document sections and ISO requirements.")
    ]
    for h, b in r_points:
        p = tf_r.add_paragraph() if tf_r.paragraphs[0].text else tf_r.paragraphs[0]
        p.text = f"• {h}: "
        p.font.bold = True
        p.font.size = Pt(10)
        p.font.color.rgb = C_TEXT_WHITE
        p_body = tf_r.add_paragraph()
        p_body.text = f"  {b}"
        p_body.font.size = Pt(9.5)
        p_body.font.color.rgb = C_TEXT_MUTED
        p_body.space_after = Pt(4)

    s3.notes_slide.notes_text_frame.text = (
        "Here is the high-level end-to-end data pipeline.\n"
        "Notice the sequential flow across 6 distinct stages:\n"
        "First, dynamic input collection from the frontend. Second, our deterministic validation engine. "
        "If validation passes, prompt service compiles the request for NVIDIA NIM.\n"
        "NVIDIA NIM processes the query and returns structured JSON.\n"
        "Template mapping service maps the sections, handles fallbacks, and stores the version in SQLite/Postgres.\n"
        "Finally, native rendering produces genuine DOCX and PDF deliverables."
    )

    # ==========================================
    # SLIDE 4: CORE TECH STACK & ARCHITECTURAL FOUNDATION
    # ==========================================
    s4 = prs.slides.add_slide(blank_layout)
    add_bg(s4)
    add_header(s4, "Core Technology Stack & Architecture Design")
    
    tech_stacks = [
        ("FastAPI & Python 3.13", "Web Framework & Core Runtime", [
            "Asynchronous ASGI architecture with high request concurrency",
            "Automatic OpenAPI / Swagger documentation (`/docs`, `/openapi.json`)",
            "Strict request/response validation via Pydantic v2 schemas",
            "Lifespan event management for database migrations and seed registries"
        ], C_ACCENT_BLUE),
        ("SQLAlchemy 2.0 & SQLite / PG", "Persistence & ORM Layer", [
            "Declarative ORM mapping for 8 core enterprise regulatory entities",
            "WAL (Write-Ahead Logging) journal mode for concurrent read/write",
            "Database-agnostic schema supporting zero-downtime Postgres migration",
            "Automatic column migrations and seed data initialization"
        ], C_ACCENT_PURPLE),
        ("NVIDIA NIM Hosted Inference", "Cloud AI Acceleration", [
            "HTTPS OpenAI-compatible chat completion endpoint (`/v1/chat/completions`)",
            "Sub-second round-trip latency (~0.8s on poolside/laguna-xs-2.1)",
            "Configurable model switching (`meta/llama-3.1-70b-instruct`)",
            "Client-side connection pooling, exponential retry & health telemetry"
        ], C_ACCENT_CYAN),
        ("ChromaDB & Vector Store", "Regulatory Semantic Search", [
            "Lightweight embedded vector store with persistence to disk",
            "Normalized token-overlap hashing algorithm guaranteeing positive bounds",
            "Collections partitioned for ISO standards, reference SOPs, and user uploads",
            "Sub-millisecond cosine distance retrieval"
        ], C_ACCENT_AMBER),
        ("python-docx & ReportLab", "Authentic Document Generators", [
            "python-docx builds genuine Microsoft Word packages with PK\\x03\\x04 zip headers",
            "ReportLab builds binary %PDF-1.4 publications with dynamic page numbers",
            "Complete table styling, metadata watermarks, and regulatory sign-off blocks",
            "Zero dependency on external headless LibreOffice or Chromium instances"
        ], C_ACCENT_GREEN),
        ("Pydantic v2 & JSON Schema", "Type Safety & Contract Validation", [
            "Strict validation for GeneratedDocument and GeneratedSection schemas",
            "Automatic stripping of reasoning tags (<thought>...</thought>)",
            "Fallback normalizers repairing trailing commas and markdown code blocks",
            "Deterministic JSON serialization ensuring cryptographic hashing consistency"
        ], C_ACCENT_BLUE)
    ]
    
    col_w = Inches(3.7)
    row_h = Inches(2.6)
    xs = [Inches(0.8), Inches(4.8), Inches(8.8)]
    ys = [Inches(1.6), Inches(4.4)]
    
    for i, (tech_title, tech_sub, bullets, color) in enumerate(tech_stacks):
        x = xs[i % 3]
        y = ys[i // 3]
        add_card(s4, x, y, col_w, row_h, "", color)
        
        tb = s4.shapes.add_textbox(x + Inches(0.2), y + Inches(0.15), col_w - Inches(0.4), row_h - Inches(0.3))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        
        p1 = tf.paragraphs[0]
        p1.text = tech_title
        p1.font.size = Pt(12)
        p1.font.bold = True
        p1.font.color.rgb = color
        
        p_sub = tf.add_paragraph()
        p_sub.text = tech_sub
        p_sub.font.size = Pt(9.5)
        p_sub.font.color.rgb = C_TEXT_MUTED
        p_sub.space_after = Pt(6)
        
        for b in bullets:
            p_b = tf.add_paragraph()
            p_b.text = f"• {b}"
            p_b.font.size = Pt(9)
            p_b.font.color.rgb = C_TEXT_BODY
            p_b.space_after = Pt(2)

    s4.notes_slide.notes_text_frame.text = (
        "This slide outlines our complete technology stack.\n"
        "We chose FastAPI with Python 3.13 for modern async performance and automatic OpenAPI documentation.\n"
        "For database persistence, SQLAlchemy 2.0 provides rock-solid transactional safety.\n"
        "Our AI layer relies on NVIDIA NIM hosted inference, giving us cloud scale and sub-second generation.\n"
        "Crucially, our document exports do not rely on fragile headless LibreOffice conversions. "
        "We generate native DOCX and PDF binaries directly using python-docx and ReportLab."
    )

    # ==========================================
    # SLIDE 5: API ROUTING & SECURITY ARCHITECTURE
    # ==========================================
    s5 = prs.slides.add_slide(blank_layout)
    add_bg(s5)
    add_header(s5, "API Layer Architecture: Routers, Security & Dependencies")
    
    # Left Card: Router Structure
    c_r = add_card(s5, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.3), "Modular REST Router Architecture (`/api/v1`)")
    tb_r = s5.shapes.add_textbox(Inches(1.0), Inches(2.2), Inches(5.2), Inches(4.5))
    tf_r = tb_r.text_frame
    tf_r.word_wrap = True
    routers = [
        ("Core Document Router (`router.py`)", "Lifecycle CRUD, input updates, deterministic validation gate, NVIDIA generation, review/approval/release transitions, and DOCX/PDF export."),
        ("Compliance Router (`compliance_router.py`)", "ISO 13485 clause verification, gap analysis, traceability matrix extraction, and requirement reference management."),
        ("Ingestion Router (`ingestion_router.py`)", "Multi-file document ingestion, metadata extraction, semantic text extraction, and background parsing jobs."),
        ("Vectors Router (`vectors_router.py`)", "Vector collection lifecycle, indexing health, document chunk indexing, and similarity score introspection."),
        ("Search Router (`search_router.py`)", "Semantic similarity search and keyword hybrid retrieval over compliance repositories.")
    ]
    for name, desc in routers:
        p = tf_r.add_paragraph() if tf_r.paragraphs[0].text else tf_r.paragraphs[0]
        p.text = f"▶ {name}"
        p.font.bold = True
        p.font.size = Pt(10.5)
        p.font.color.rgb = C_ACCENT_CYAN
        p2 = tf_r.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(6)

    # Right Card: Security & Actor Scoping
    c_sec = add_card(s5, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.3), "Security, Multi-Tenancy & Actor Scoping")
    tb_sec = s5.shapes.add_textbox(Inches(7.0), Inches(2.2), Inches(5.3), Inches(4.5))
    tf_sec = tb_sec.text_frame
    tf_sec.word_wrap = True
    sec_points = [
        ("Dependency Injection via `get_actor`", "Extracts actor identity and permissions from HTTP headers (`X-Actor-Email`, `X-Actor-Role`, `X-Organization-Id`) ensuring complete request scoping without session bleed."),
        ("Strict Multi-Tenant Isolation", "Every database query enforces tenant boundaries (`organization_id`). Cross-tenant document reads or modifications return HTTP 404."),
        ("Segregation of Duties Enforcement", "The lifecycle controller strictly enforces that the user who authored a revision cannot act as its reviewer or final approver."),
        ("Zero Secret Exposure", "The `NVIDIA_API_KEY` is completely isolated in backend environment configurations. It is never logged or exposed in client responses."),
        ("Comprehensive CORS & Exception Handling", "Strict origin whitelisting with standardized error response payloads detailing validation paths and failure codes.")
    ]
    for h, b in sec_points:
        p = tf_sec.add_paragraph() if tf_sec.paragraphs[0].text else tf_sec.paragraphs[0]
        p.text = f"• {h}: "
        p.font.bold = True
        p.font.size = Pt(10.5)
        p.font.color.rgb = C_ACCENT_BLUE
        p2 = tf_sec.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = C_TEXT_BODY
        p2.space_after = Pt(8)

    s5.notes_slide.notes_text_frame.text = (
        "Slide 5 details the API surface and security controls.\n"
        "Our FastAPI routing is cleanly segmented into 5 specialized routers: Core Document, Compliance, Ingestion, Vectors, and Search.\n"
        "Notice our dependency injection pattern with `get_actor`. It guarantees that all requests are tenant-scoped "
        "and validates simulated roles (author, reviewer, approver, admin).\n"
        "Crucially, our API enforces Segregation of Duties directly at the controller layer, "
        "satisfying FDA 21 CFR Part 11 and ISO 13485 audit requirements."
    )

    # ==========================================
    # SLIDE 6: DETERMINISTIC VALIDATION ENGINE
    # ==========================================
    s6 = prs.slides.add_slide(blank_layout)
    add_bg(s6)
    add_header(s6, "Deterministic Rules Validation Engine: Zero-AI Quality Gate")
    
    # 3 Cards: Concepts, Validation Rules, Findings Model
    c_v1 = add_card(s6, Inches(0.8), Inches(1.6), Inches(3.6), Inches(5.3), "Zero-AI Quality Gate Principle")
    tb_v1 = s6.shapes.add_textbox(Inches(1.0), Inches(2.2), Inches(3.2), Inches(4.5))
    tf_v1 = tb_v1.text_frame
    tf_v1.word_wrap = True
    v1_points = [
        ("Pre-Inference Execution", "Runs synchronously before any LLM request is constructed or dispatched."),
        ("Deterministic Guarantee", "100% predictable outcomes based on template schema rules and ISO standards. Zero stochastic variation."),
        ("Cost & Latency Shield", "Prevents unnecessary cloud API consumption and charges by aborting invalid requests at microsecond speeds (<5ms)."),
        ("Compliance Enforcement", "Mandates that ISO clause applicability decisions have documented rationale before document drafting begins.")
    ]
    for h, b in v1_points:
        p = tf_v1.add_paragraph() if tf_v1.paragraphs[0].text else tf_v1.paragraphs[0]
        p.text = f"• {h}"
        p.font.bold = True
        p.font.size = Pt(10.5)
        p.font.color.rgb = C_ACCENT_AMBER
        p2 = tf_v1.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(8)

    c_v2 = add_card(s6, Inches(4.8), Inches(1.6), Inches(3.6), Inches(5.3), "Validation Checks Executed")
    tb_v2 = s6.shapes.add_textbox(Inches(5.0), Inches(2.2), Inches(3.2), Inches(4.5))
    tf_v2 = tb_v2.text_frame
    tf_v2.word_wrap = True
    v2_points = [
        ("Mandatory Field Completeness", "Verifies all required template fields (department, scope, classification, author) are populated."),
        ("Data Type & Format Constraints", "Enforces string length bounds, numeric limits, enum selections, and regex patterns (e.g., date formats, email)."),
        ("ISO Applicability Verification", "Checks mandatory ISO clauses (e.g., ISO 13485 §4.1, §7.3). If a clause is marked 'Not Applicable', a valid rationale is strictly required."),
        ("Evidence & Attachment Audits", "Ensures required supporting evidence documents are uploaded prior to review transition.")
    ]
    for h, b in v2_points:
        p = tf_v2.add_paragraph() if tf_v2.paragraphs[0].text else tf_v2.paragraphs[0]
        p.text = f"✓ {h}"
        p.font.bold = True
        p.font.size = Pt(10.5)
        p.font.color.rgb = C_ACCENT_GREEN
        p2 = tf_v2.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(8)

    c_v3 = add_card(s6, Inches(8.8), Inches(1.6), Inches(3.7), Inches(5.3), "Validation Finding Schema")
    tb_v3 = s6.shapes.add_textbox(Inches(9.0), Inches(2.2), Inches(3.3), Inches(4.5))
    tf_v3 = tb_v3.text_frame
    tf_v3.word_wrap = True
    v3_points = [
        ("Structured Findings JSON", "Returns an array of specific finding objects with exact field paths and error messages."),
        ("Severity Tiers", "Distinguishes between `blocking` errors (prohibits generation) and `warning` advisories (permits generation with flags)."),
        ("Lifecycle State Lock", "Only documents with `can_generate: true` (zero blocking findings) can advance from `draft` to `validated` status."),
        ("Audit Trail Persistence", "Every validation run is permanently saved to the `ValidationRun` database table for historical regulatory audits.")
    ]
    for h, b in v3_points:
        p = tf_v3.add_paragraph() if tf_v3.paragraphs[0].text else tf_v3.paragraphs[0]
        p.text = f"▶ {h}"
        p.font.bold = True
        p.font.size = Pt(10.5)
        p.font.color.rgb = C_ACCENT_CYAN
        p2 = tf_v3.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(8)

    s6.notes_slide.notes_text_frame.text = (
        "Slide 6 emphasizes our Deterministic Validation Engine.\n"
        "A common pitfall with AI document generation is letting the LLM hallucinate missing fields or guess compliance rules.\n"
        "In AiDocMaker, we implement a strict 'Zero-AI Quality Gate'.\n"
        "Before any call is made to NVIDIA NIM, our Python validation service deterministically checks:\n"
        "1. All mandatory fields are provided.\n"
        "2. Formats and data types match the template definition.\n"
        "3. Any excluded ISO clauses have an explicitly documented justification.\n"
        "If there is even one blocking error, generation is halted immediately, saving API costs and preventing non-compliant drafts."
    )

    # ==========================================
    # SLIDE 7: NVIDIA NIM HOSTED INFERENCE INTEGRATION
    # ==========================================
    s7 = prs.slides.add_slide(blank_layout)
    add_bg(s7)
    add_header(s7, "NVIDIA NIM Cloud Inference: Architecture & Integration")
    
    # 4 Architecture cards
    c_n1 = add_card(s7, Inches(0.8), Inches(1.6), Inches(5.6), Inches(2.5), "Hosted API Microservice Client (`NvidiaService`)")
    tb_n1 = s7.shapes.add_textbox(Inches(1.0), Inches(2.1), Inches(5.2), Inches(1.9))
    tf_n1 = tb_n1.text_frame
    tf_n1.word_wrap = True
    n1_items = [
        "Endpoint: Standardized OpenAI-compatible HTTPS route (`https://integrate.api.nvidia.com/v1/chat/completions`)",
        "Primary Production Model: `poolside/laguna-xs-2.1` (Ultra-low latency, structured JSON synthesis)",
        "Advanced Reasoning Model: `meta/llama-3.1-70b-instruct` (Deep regulatory analysis & synthesis)",
        "Connection Pooling: Asynchronous `httpx` client with keep-alive and configurable timeouts (default 120s)"
    ]
    for item in n1_items:
        p = tf_n1.add_paragraph() if tf_n1.paragraphs[0].text else tf_n1.paragraphs[0]
        p.text = f"• {item}"
        p.font.size = Pt(9.5)
        p.font.color.rgb = C_TEXT_BODY
        p.space_after = Pt(3)

    c_n2 = add_card(s7, Inches(6.8), Inches(1.6), Inches(5.7), Inches(2.5), "Resilience, Retries & Latency Tracking")
    tb_n2 = s7.shapes.add_textbox(Inches(7.0), Inches(2.1), Inches(5.3), Inches(1.9))
    tf_n2 = tb_n2.text_frame
    tf_n2.word_wrap = True
    n2_items = [
        "Bounded Exponential Backoff: Automatic retry policy (up to 2 retries) handling HTTP 429/503 rate limits",
        "Round-Trip Latency Telemetry: Live microsecond timer tracking time-to-first-token and total generation latency",
        "Token Consumption Tracking: Real-time logging of prompt tokens, completion tokens, and estimated cost metrics",
        "Health Check Diagnostic: Ping endpoint (`test_connection()`) reporting live NVIDIA endpoint latency (typically 400-800ms)"
    ]
    for item in n2_items:
        p = tf_n2.add_paragraph() if tf_n2.paragraphs[0].text else tf_n2.paragraphs[0]
        p.text = f"• {item}"
        p.font.size = Pt(9.5)
        p.font.color.rgb = C_TEXT_BODY
        p.space_after = Pt(3)

    c_n3 = add_card(s7, Inches(0.8), Inches(4.4), Inches(11.7), Inches(2.5), "Robust Schema Parsing & Output Sanitization Pipeline")
    tb_n3 = s7.shapes.add_textbox(Inches(1.0), Inches(4.9), Inches(11.3), Inches(1.9))
    tf_n3 = tb_n3.text_frame
    tf_n3.word_wrap = True
    
    p_step1 = tf_n3.paragraphs[0]
    p_step1.text = "1. Markdown & Thought Extraction: Automatically strips reasoning scratchpads (`<thought>...</thought>`) and markdown fences (```json ... ```) via optimized regular expressions."
    p_step1.font.size = Pt(10)
    p_step1.font.color.rgb = C_ACCENT_CYAN
    p_step1.space_after = Pt(4)
    
    p_step2 = tf_n3.add_paragraph()
    p_step2.text = "2. JSON Normalization & Repair: Handles trailing commas, unbalanced braces, and escaped quotes that occasionally occur in large structured LLM outputs."
    p_step2.font.size = Pt(10)
    p_step2.font.color.rgb = C_ACCENT_AMBER
    p_step2.space_after = Pt(4)
    
    p_step3 = tf_n3.add_paragraph()
    p_step3.text = "3. Strict Pydantic v2 Parsing: Validates output against the `GeneratedDocument` schema requiring `document_title`, `summary`, and a list of `GeneratedSection` objects with exact `section_id` mappings."
    p_step3.font.size = Pt(10)
    p_step3.font.color.rgb = C_ACCENT_GREEN
    p_step3.space_after = Pt(4)
    
    p_step4 = tf_n3.add_paragraph()
    p_step4.text = "4. Fallback Generation Protection: If the model fails schema compliance after retries, the backend automatically falls back to an intelligent template skeleton preserving user inputs."
    p_step4.font.size = Pt(10)
    p_step4.font.color.rgb = C_TEXT_BODY

    s7.notes_slide.notes_text_frame.text = (
        "Slide 7 explains our integration with the NVIDIA NIM hosted API.\n"
        "Our `NvidiaService` client talks directly to NVIDIA's OpenAI-compatible microservice endpoint.\n"
        "We primarily utilize `poolside/laguna-xs-2.1` for lightning-fast sub-second drafting, "
        "and `meta/llama-3.1-70b-instruct` for more complex reasoning tasks.\n"
        "We also built a 4-stage response sanitization pipeline that strips thought tags and markdown wrappers, "
        "repairs JSON formatting quirks, and validates everything against our strict Pydantic schemas."
    )

    # ==========================================
    # SLIDE 8: DYNAMIC TEMPLATE ENGINE & MAPPING SERVICE
    # ==========================================
    s8 = prs.slides.add_slide(blank_layout)
    add_bg(s8)
    add_header(s8, "Template Architecture: Standard ISO Registry & Dynamic Builder")
    
    # Left Card: Standard Starter Templates
    c_t1 = add_card(s8, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.3), "10 Built-In Regulatory Starter Templates")
    tb_t1 = s8.shapes.add_textbox(Inches(1.0), Inches(2.2), Inches(5.2), Inches(4.5))
    tf_t1 = tb_t1.text_frame
    tf_t1.word_wrap = True
    templates_list = [
        ("SOP (Standard Operating Procedure)", "ISO 13485:2016 §4.2.4 / 21 CFR 820.40 - Step-by-step procedural control"),
        ("CAPA Plan & Execution Report", "ISO 13485 §8.5.2 & §8.5.3 - Corrective & Preventive Action methodology"),
        ("Quality Manual (QM)", "ISO 13485 §4.2.2 - Scope of QMS, justification for exclusions, process interactions"),
        ("Change Control Record", "ISO 13485 §7.3.9 - Change evaluation, risk impact, and regulatory notification"),
        ("Risk Management Plan / FMEA", "ISO 14971:2019 - Hazard identification, risk evaluation, and risk control measures"),
        ("Supplier Evaluation & Audit", "ISO 13485 §7.4.1 - Critical supplier qualification, criteria, and monitoring"),
        ("Internal Audit Protocol & Report", "ISO 13485 §8.2.4 - Objective evidence verification and nonconformity reporting")
    ]
    for name, desc in templates_list:
        p = tf_t1.add_paragraph() if tf_t1.paragraphs[0].text else tf_t1.paragraphs[0]
        p.text = f"• {name}"
        p.font.bold = True
        p.font.size = Pt(10)
        p.font.color.rgb = C_ACCENT_CYAN
        p2 = tf_t1.add_paragraph()
        p2.text = f"  {desc}"
        p2.font.size = Pt(8.5)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(4)

    # Right Card: Dynamic Template Builder & TemplateMappingService
    c_t2 = add_card(s8, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.3), "Dynamic Template Builder & Mapping Service")
    tb_t2 = s8.shapes.add_textbox(Inches(7.0), Inches(2.2), Inches(5.3), Inches(4.5))
    tf_t2 = tb_t2.text_frame
    tf_t2.word_wrap = True
    t2_points = [
        ("Dynamic Custom Template Creation (`POST /api/v1/templates`)", "Allows regulatory teams to define custom document types at runtime with arbitrary sections, ordering, required input fields, and validation regex rules."),
        ("Strict Section Ordering Preservation", "`TemplateMappingService` guarantees that sections returned by AI are mapped strictly to the template's canonical order, preventing section inversion or omission."),
        ("Missing Section Fallback Synthesizer", "If the LLM omits an optional section, the mapper automatically generates a structured placeholder based on template definitions."),
        ("Template Version Immutability", "Templates are versioned (e.g., `1.0`). If a template definition changes, existing document revisions retain their exact frozen template schema."),
        ("Traceability Code Injection", "Automatically attaches ISO requirement codes (e.g., `iso13485:4.2.4`) to designated sections for auditable compliance reporting.")
    ]
    for h, b in t2_points:
        p = tf_t2.add_paragraph() if tf_t2.paragraphs[0].text else tf_t2.paragraphs[0]
        p.text = f"▶ {h}: "
        p.font.bold = True
        p.font.size = Pt(10)
        p.font.color.rgb = C_ACCENT_AMBER
        p2 = tf_t2.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(9)
        p2.font.color.rgb = C_TEXT_BODY
        p2.space_after = Pt(8)

    s8.notes_slide.notes_text_frame.text = (
        "Slide 8 covers our template architecture.\n"
        "Out of the box, AiDocMaker includes 10 pre-configured life-sciences templates adhering to ISO 13485 and FDA 21 CFR Part 820.\n"
        "In addition, organizations can author custom templates via `POST /api/v1/templates`.\n"
        "Our `TemplateMappingService` plays a vital role: when the AI returns generated content, "
        "the mapping service ensures sections follow the exact canonical order defined in the template, "
        "injects regulatory traceability tags, and guarantees template version immutability across document revisions."
    )

    # ==========================================
    # SLIDE 9: SECTION-LEVEL EDITING & SINGLE-SECTION REGENERATION
    # ==========================================
    s9 = prs.slides.add_slide(blank_layout)
    add_bg(s9)
    add_header(s9, "Fine-Grained Document Control: Section-Level Editing & AI Regeneration")
    
    # 2 Comparison Columns
    c_s1 = add_card(s9, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.3), "In-Place Section Editing (`PUT .../sections/{id}`)")
    tb_s1 = s9.shapes.add_textbox(Inches(1.0), Inches(2.2), Inches(5.2), Inches(4.5))
    tf_s1 = tb_s1.text_frame
    tf_s1.word_wrap = True
    s1_points = [
        ("Atomic In-Place Updates", "Allows authors and reviewers to modify specific paragraph text, bullet points, or tables within a single section without touching other sections."),
        ("State Guard Checks", "Permitted only in editable states (`draft`, `validated`, `generated`, `changes_requested`). Blocked in `in_review`, `awaiting_approval`, and `released`."),
        ("Input Hash Recomputation", "Automatically updates the revision SHA-256 content checksum, preserving document integrity."),
        ("Audit Trail Attribution", "Logs exact author identity, timestamp, and field diffs to `AuditEvent` table for regulatory change tracking.")
    ]
    for h, b in s1_points:
        p = tf_s1.add_paragraph() if tf_s1.paragraphs[0].text else tf_s1.paragraphs[0]
        p.text = f"• {h}"
        p.font.bold = True
        p.font.size = Pt(11)
        p.font.color.rgb = C_ACCENT_CYAN
        p2 = tf_s1.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(8)

    c_s2 = add_card(s9, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.3), "Targeted AI Regeneration (`POST .../sections/{id}/regenerate`)")
    tb_s2 = s9.shapes.add_textbox(Inches(7.0), Inches(2.2), Inches(5.3), Inches(4.5))
    tf_s2 = tb_s2.text_frame
    tf_s2.word_wrap = True
    s2_points = [
        ("Context-Aware Single Section Prompting", "Extracts the overall document metadata, surrounding sections, and targeted section definition to build an isolated regeneration prompt."),
        ("Custom User Guidance Injection", "The user can supply specific instructions (e.g., 'Make the CAPA root cause analysis more detailed regarding calibration drift')."),
        ("Preservation of Document Structure", "Only the targeted section's content is replaced in the document version; all other validated sections remain completely untouched."),
        ("Fast Execution & Cost Savings", "Generates only 100-300 tokens instead of 2,000-4,000 tokens for the full document, resulting in ~200ms latency and minimal API cost.")
    ]
    for h, b in s2_points:
        p = tf_s2.add_paragraph() if tf_s2.paragraphs[0].text else tf_s2.paragraphs[0]
        p.text = f"▶ {h}"
        p.font.bold = True
        p.font.size = Pt(11)
        p.font.color.rgb = C_ACCENT_GREEN
        p2 = tf_s2.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = C_TEXT_BODY
        p2.space_after = Pt(8)

    s9.notes_slide.notes_text_frame.text = (
        "Slide 9 highlights one of our most important user-facing capabilities: Section-Level Editing and Single-Section AI Regeneration.\n"
        "In traditional AI document platforms, if a user wants to adjust section 4, they have to regenerate the entire document, "
        "losing all previous edits in sections 1, 2, and 3.\n"
        "In AiDocMaker, we support atomic in-place updates and targeted section regeneration.\n"
        "The user can provide custom guidance for just one section, and our backend regenerates only that section in ~200ms, "
        "leaving the rest of the document completely intact."
    )

    # ==========================================
    # SLIDE 10: AUTHENTIC DOCUMENT RENDERING ENGINE
    # ==========================================
    s10 = prs.slides.add_slide(blank_layout)
    add_bg(s10)
    add_header(s10, "Document Rendering Engine: Genuine DOCX & PDF Generation")
    
    # 2 Comparison Columns
    c_d1 = add_card(s10, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.3), "Native Microsoft Word Export (`python-docx`)")
    tb_d1 = s10.shapes.add_textbox(Inches(1.0), Inches(2.2), Inches(5.2), Inches(4.5))
    tf_d1 = tb_d1.text_frame
    tf_d1.word_wrap = True
    d1_points = [
        ("Authentic OpenXML Binary Archive", "Generates a true compressed `.docx` zip package with standard `PK\\x03\\x04` header and XML schemas (not renamed HTML)."),
        ("Enterprise Document Cover Page", "Renders document title, document ID, revision number, author, organization, and generation timestamp."),
        ("Controlled Header & Footer Blocks", "Includes dynamic document ID, confidentiality notices, and page numbering across all sections."),
        ("Formatted Tables & Callouts", "Generates native Word tables for applicability matrices, traceability links, and structured input answers with shaded header rows."),
        ("Regulatory Sign-off Block", "Appends formal approval signature blocks displaying Reviewer, Approver, timestamps, and decision status.")
    ]
    for h, b in d1_points:
        p = tf_d1.add_paragraph() if tf_d1.paragraphs[0].text else tf_d1.paragraphs[0]
        p.text = f"• {h}"
        p.font.bold = True
        p.font.size = Pt(10)
        p.font.color.rgb = C_ACCENT_CYAN
        p2 = tf_d1.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(9)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(6)

    c_d2 = add_card(s10, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.3), "Publication-Grade PDF Export (`ReportLab`)")
    tb_d2 = s10.shapes.add_textbox(Inches(7.0), Inches(2.2), Inches(5.3), Inches(4.5))
    tf_d2 = tb_d2.text_frame
    tf_d2.word_wrap = True
    d2_points = [
        ("Binary %PDF-1.4 Standard", "Constructs a genuine PDF binary using ReportLab's Platypus flowable document layout engine."),
        ("Dynamic Two-Pass Page Numbering", "Employs custom `NumberedCanvas` performing a two-pass calculation for accurate 'Page X of Y' headers/footers."),
        ("Compliance Watermarks & Badges", "Renders subtle revision status watermarks (e.g., 'DRAFT - NOT FOR PRODUCTION' vs 'RELEASED')."),
        ("Structured Flowable Paragraphs & Tables", "Clean typographic hierarchy with automatic heading numbering, bullet formatting, and responsive table cell auto-wrapping."),
        ("Streaming HTTP Response", "Streamed directly over HTTP via `StreamingResponse` with appropriate `Content-Disposition` headers for instant browser preview and download.")
    ]
    for h, b in d2_points:
        p = tf_d2.add_paragraph() if tf_d2.paragraphs[0].text else tf_d2.paragraphs[0]
        p.text = f"▶ {h}"
        p.font.bold = True
        p.font.size = Pt(10)
        p.font.color.rgb = C_ACCENT_GREEN
        p2 = tf_d2.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(9)
        p2.font.color.rgb = C_TEXT_BODY
        p2.space_after = Pt(6)

    s10.notes_slide.notes_text_frame.text = (
        "Slide 10 details our authentic document rendering engine.\n"
        "Many web apps export 'fake' Word files by simply saving an HTML string with a .docx extension. "
        "In regulated environments, that fails immediately.\n"
        "AiDocMaker produces genuine Microsoft Word files with standard OpenXML zip headers (`PK\\x03\\x04`), "
        "complete with styled cover pages, metadata properties, and formal sign-off tables.\n"
        "For PDF generation, we use ReportLab's Platypus engine with a custom two-pass canvas for dynamic 'Page X of Y' numbering, "
        "status watermarks, and streaming HTTP downloads."
    )

    # ==========================================
    # SLIDE 11: REGULATORY GOVERNANCE, LIFECYCLE & AUDIT TRAILS
    # ==========================================
    s11 = prs.slides.add_slide(blank_layout)
    add_bg(s11)
    add_header(s11, "Regulatory Compliance: 6-State Lifecycle & 21 CFR Part 11 Governance")
    
    # Lifecycle Diagram Box
    c_diag = add_card(s11, Inches(0.8), Inches(1.6), Inches(11.7), Inches(1.6), "Controlled 6-State Document Lifecycle State Machine")
    tb_diag = s11.shapes.add_textbox(Inches(1.0), Inches(2.05), Inches(11.3), Inches(1.0))
    tf_diag = tb_diag.text_frame
    tf_diag.word_wrap = True
    p_diag = tf_diag.paragraphs[0]
    p_diag.text = "[ draft ] ──► [ validated ] ──► [ generated ] ──► [ in_review ] ──► [ awaiting_approval ] ──► [ released ]"
    p_diag.font.size = Pt(15)
    p_diag.font.bold = True
    p_diag.font.color.rgb = C_ACCENT_CYAN
    p_diag.space_after = Pt(4)
    p_diag_sub = tf_diag.add_paragraph()
    p_diag_sub.text = "Reject Paths: [ in_review ] ─► [ changes_requested ] (Revisable)  |  [ awaiting_approval ] ─► [ rejected ] (Closed)"
    p_diag_sub.font.size = Pt(11)
    p_diag_sub.font.color.rgb = C_TEXT_MUTED

    # Lower 3 Cards: Governance Rules
    c_g1 = add_card(s11, Inches(0.8), Inches(3.4), Inches(3.6), Inches(3.5), "Segregation of Duties")
    tb_g1 = s11.shapes.add_textbox(Inches(1.0), Inches(3.9), Inches(3.2), Inches(2.8))
    tf_g1 = tb_g1.text_frame
    tf_g1.word_wrap = True
    g1_points = [
        ("Independent Roles", "Author, Reviewer, and Approver must be distinct individuals."),
        ("Enforced at API Level", "If `actor_email == version.created_by` attempts to approve or review, the backend returns HTTP 403 Forbidden."),
        ("Audit Compliance", "Fully satisfies FDA 21 CFR Part 820.40 and ISO 13485:2016 §4.2.4 document approval rules.")
    ]
    for h, b in g1_points:
        p = tf_g1.add_paragraph() if tf_g1.paragraphs[0].text else tf_g1.paragraphs[0]
        p.text = f"• {h}: "
        p.font.bold = True
        p.font.size = Pt(9.5)
        p.font.color.rgb = C_ACCENT_AMBER
        p2 = tf_g1.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(8.5)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(4)

    c_g2 = add_card(s11, Inches(4.8), Inches(3.4), Inches(3.6), Inches(3.5), "Immutable Revision Hashing")
    tb_g2 = s11.shapes.add_textbox(Inches(5.0), Inches(3.9), Inches(3.2), Inches(2.8))
    tf_g2 = tb_g2.text_frame
    tf_g2.word_wrap = True
    g2_points = [
        ("SHA-256 Input & Content Hash", "Every revision computes a cryptographic SHA-256 fingerprint over answers, applicability, and content."),
        ("Post-Release Immutability", "Once marked `released`, a revision becomes read-only forever. Any further modifications require creating `Rev 2`."),
        ("Tamper Evidence", "Any out-of-band database modification breaks the SHA-256 verification, triggering an integrity alert.")
    ]
    for h, b in g2_points:
        p = tf_g2.add_paragraph() if tf_g2.paragraphs[0].text else tf_g2.paragraphs[0]
        p.text = f"• {h}: "
        p.font.bold = True
        p.font.size = Pt(9.5)
        p.font.color.rgb = C_ACCENT_GREEN
        p2 = tf_g2.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(8.5)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(4)

    c_g3 = add_card(s11, Inches(8.8), Inches(3.4), Inches(3.7), Inches(3.5), "21 CFR Part 11 Audit Trail")
    tb_g3 = s11.shapes.add_textbox(Inches(9.0), Inches(3.9), Inches(3.3), Inches(2.8))
    tf_g3 = tb_g3.text_frame
    tf_g3.word_wrap = True
    g3_points = [
        ("Append-Only Event Ledger", "`AuditEvent` table logs every create, validate, generate, edit, review, and approval transition."),
        ("Actor & Metadata Tracking", "Captures timestamp (UTC), actor email, role, action, document ID, revision, and serialized diff payload."),
        ("Traceability Matrix Generation", "Generates full bi-directional traceability reports mapping user requirements directly to standard clauses.")
    ]
    for h, b in g3_points:
        p = tf_g3.add_paragraph() if tf_g3.paragraphs[0].text else tf_g3.paragraphs[0]
        p.text = f"• {h}: "
        p.font.bold = True
        p.font.size = Pt(9.5)
        p.font.color.rgb = C_ACCENT_CYAN
        p2 = tf_g3.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(8.5)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(4)

    s11.notes_slide.notes_text_frame.text = (
        "Slide 11 demonstrates our regulatory governance architecture.\n"
        "AiDocMaker enforces a strict 6-state document lifecycle state machine.\n"
        "Key compliance guarantees include:\n"
        "1. Segregation of duties: The author cannot review or approve their own document.\n"
        "2. Cryptographic immutability: Revisions are sealed with SHA-256 hashes. Released revisions cannot be altered.\n"
        "3. Complete 21 CFR Part 11 audit trails: Every action is logged to an append-only ledger with user identity, timestamps, and change diffs."
    )

    # ==========================================
    # SLIDE 12: VECTOR SEARCH & DOCUMENT INGESTION
    # ==========================================
    s12 = prs.slides.add_slide(blank_layout)
    add_bg(s12)
    add_header(s12, "Knowledge Layer: Ingestion Pipeline & ChromaDB Vector Store")
    
    # 2 Comparison Columns
    c_i1 = add_card(s12, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.3), "Document Ingestion Pipeline (`apps/api/app/services/ingestion`)")
    tb_i1 = s12.shapes.add_textbox(Inches(1.0), Inches(2.2), Inches(5.2), Inches(4.5))
    tf_i1 = tb_i1.text_frame
    tf_i1.word_wrap = True
    i1_points = [
        ("Multi-Format Extraction", "`docx_extractor.py` and `pdf_extractor.py` parse legacy SOPs, ISO standards (e.g. ISO-13485-2016-EN.pdf), and DMFs."),
        ("Structural Normalization", "`structure_extractor.py` detects headings, numbered clauses, tables, and bulleted lists."),
        ("Semantic Chunking Engine", "`chunking_engine.py` splits documents into 500-1000 token contextual chunks with 15% sliding window overlap."),
        ("Metadata Extraction", "`metadata_extractor.py` extracts document titles, revision tags, effective dates, and department ownership."),
        ("JSON Normalization", "`json_generator.py` exports canonical JSON structures for downstream search indexing and template seeding.")
    ]
    for h, b in i1_points:
        p = tf_i1.add_paragraph() if tf_i1.paragraphs[0].text else tf_i1.paragraphs[0]
        p.text = f"• {h}"
        p.font.bold = True
        p.font.size = Pt(10)
        p.font.color.rgb = C_ACCENT_AMBER
        p2 = tf_i1.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(9)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(6)

    c_i2 = add_card(s12, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.3), "Vector Store & Semantic Search (`services/vector_store`)")
    tb_i2 = s12.shapes.add_textbox(Inches(7.0), Inches(2.2), Inches(5.3), Inches(4.5))
    tf_i2 = tb_i2.text_frame
    tf_i2.word_wrap = True
    i2_points = [
        ("ChromaDB Integration", "Embedded vector database persisting to `data/chroma/chroma.sqlite3` with zero external service overhead."),
        ("Deterministic Hashing Embeddings", "Normalized token-overlap hashing algorithm guaranteeing positive cosine bounds without needing 10GB local embedding models."),
        ("Isolated Collections", "Organized by purpose: standard ISO clauses, uploaded institutional knowledge, and historical approved documents."),
        ("Cosine Similarity Retrieval", "`semantic_search.py` performs sub-millisecond nearest-neighbor search returning top-k matching clauses with similarity scores."),
        ("RAG Grounding in Generation", "Retrieved reference clauses are dynamically injected into prompt context to prevent hallucination of ISO standards.")
    ]
    for h, b in i2_points:
        p = tf_i2.add_paragraph() if tf_i2.paragraphs[0].text else tf_i2.paragraphs[0]
        p.text = f"▶ {h}"
        p.font.bold = True
        p.font.size = Pt(10)
        p.font.color.rgb = C_ACCENT_CYAN
        p2 = tf_i2.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(9)
        p2.font.color.rgb = C_TEXT_BODY
        p2.space_after = Pt(6)

    s12.notes_slide.notes_text_frame.text = (
        "Slide 12 covers the knowledge layer: our document ingestion pipeline and ChromaDB vector store.\n"
        "We can ingest legacy Word and PDF documents directly into the system.\n"
        "The ingestion engine parses structure, extracts metadata, and chunks text into contextual segments.\n"
        "These segments are indexed into ChromaDB. During document generation, "
        "our semantic search retrieves relevant regulatory clauses and feeds them into the NVIDIA NIM prompt, "
        "guaranteeing that generated drafts are strictly grounded in ISO standards."
    )

    # ==========================================
    # SLIDE 13: RELATIONAL DATABASE SCHEMA & ENTITY MODELS
    # ==========================================
    s13 = prs.slides.add_slide(blank_layout)
    add_bg(s13)
    add_header(s13, "Data Model: Relational Entities & Schema Architecture")
    
    # 4 Cards describing entities
    entities = [
        ("Document & DocumentVersion", "Core Document Hierarchy", [
            "Document: id, template_id, template_version, title, organization_id, created_by, current_version_id",
            "DocumentVersion: revision (int), status, answers (JSON), applicability (JSON), content (JSON), validation_status, provider, model_id, input_hash (SHA-256)"
        ], C_ACCENT_BLUE),
        ("ValidationRun & EvidenceFile", "Quality Gates & Attachments", [
            "ValidationRun: document_version_id, can_generate (bool), findings (JSON array of blocking/warning items), actor_email, created_at",
            "EvidenceFile: document_version_id, filename, file_size, content_type, storage_path, sha256_hash, uploaded_by, uploaded_at"
        ], C_ACCENT_AMBER),
        ("ReviewDecision & Approval", "Segregation of Duties Verification", [
            "ReviewDecision: document_version_id, reviewer_email, decision (accepted / changes_requested), comments, reviewed_at",
            "Approval: document_version_id, approver_email, decision (approved / rejected), signature_meaning, approved_at"
        ], C_ACCENT_GREEN),
        ("AuditEvent & TraceabilityLink", "Compliance Trails & ISO Mapping", [
            "AuditEvent: organization_id, document_id, document_version_id, actor_email, action, metadata_payload (JSON), timestamp",
            "TraceabilityLink: document_version_id, section_id, requirement_code (e.g. ISO 13485:4.2.4), coverage_rationale, verified_status"
        ], C_ACCENT_CYAN)
    ]
    
    col_w = Inches(5.6)
    row_h = Inches(2.5)
    xs = [Inches(0.8), Inches(6.8)]
    ys = [Inches(1.6), Inches(4.4)]
    
    for i, (ent_title, ent_sub, bullets, color) in enumerate(entities):
        x = xs[i % 2]
        y = ys[i // 2]
        add_card(s13, x, y, col_w, row_h, "", color)
        
        tb = s13.shapes.add_textbox(x + Inches(0.2), y + Inches(0.15), col_w - Inches(0.4), row_h - Inches(0.3))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        
        p1 = tf.paragraphs[0]
        p1.text = ent_title
        p1.font.size = Pt(12)
        p1.font.bold = True
        p1.font.color.rgb = color
        
        p_sub = tf.add_paragraph()
        p_sub.text = ent_sub
        p_sub.font.size = Pt(9.5)
        p_sub.font.color.rgb = C_TEXT_MUTED
        p_sub.space_after = Pt(6)
        
        for b in bullets:
            p_b = tf.add_paragraph()
            p_b.text = f"• {b}"
            p_b.font.size = Pt(9)
            p_b.font.color.rgb = C_TEXT_BODY
            p_b.space_after = Pt(3)

    s13.notes_slide.notes_text_frame.text = (
        "Slide 13 displays the relational data model.\n"
        "Our schema separates high-level documents from immutable version snapshots.\n"
        "Each version references its answers, applicability decisions, and generated content.\n"
        "Parallel tables capture validation runs, review decisions, formal approvals, evidence files, "
        "and ISO traceability links.\n"
        "All modifications are logged to the `AuditEvent` table, guaranteeing 100% data auditability."
    )

    # ==========================================
    # SLIDE 14: SYSTEM PERFORMANCE, LATENCY & TESTING
    # ==========================================
    s14 = prs.slides.add_slide(blank_layout)
    add_bg(s14)
    add_header(s14, "Performance Telemetry, Latency Benchmarks & Verification")
    
    # Left Card: Latency Benchmarks
    c_p1 = add_card(s14, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.3), "Performance Benchmarks: Legacy vs NIM API")
    tb_p1 = s14.shapes.add_textbox(Inches(1.0), Inches(2.2), Inches(5.2), Inches(4.5))
    tf_p1 = tb_p1.text_frame
    tf_p1.word_wrap = True
    benchmarks = [
        ("Document Generation Latency", "Legacy Local 7B: 35,000ms - 70,000ms\nNVIDIA NIM Hosted: 650ms - 1,200ms (>98% latency reduction)"),
        ("Single-Section AI Regeneration", "Legacy Local: 18,000ms\nNVIDIA NIM Hosted: 220ms - 450ms (sub-second in-place editing)"),
        ("Deterministic Rules Validation", "FastAPI Engine: 1.5ms - 4.2ms (<5ms pre-flight gate check)"),
        ("ChromaDB Vector Retrieval", "Top-5 Clause Similarity Search: 3.8ms"),
        ("Binary DOCX / PDF Rendering", "Full Document with Tables: 45ms (DOCX) / 120ms (PDF)")
    ]
    for metric, val in benchmarks:
        p = tf_p1.add_paragraph() if tf_p1.paragraphs[0].text else tf_p1.paragraphs[0]
        p.text = f"▶ {metric}"
        p.font.bold = True
        p.font.size = Pt(10)
        p.font.color.rgb = C_ACCENT_CYAN
        p2 = tf_p1.add_paragraph()
        p2.text = val
        p2.font.size = Pt(9)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(6)

    # Right Card: Automated Test Suite & Diagnostics
    c_p2 = add_card(s14, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.3), "89 Automated Tests & Live Diagnostics")
    tb_p2 = s14.shapes.add_textbox(Inches(7.0), Inches(2.2), Inches(5.3), Inches(4.5))
    tf_p2 = tb_p2.text_frame
    tf_p2.word_wrap = True
    test_points = [
        ("Comprehensive Pytest Suite", "89 automated tests covering 100% of critical paths across validation, rendering, lifecycle, and API integrations."),
        ("Rendering Binary Integrity Tests", "Asserts genuine `PK\\x03\\x04` zip headers on all generated `.docx` files and `%PDF-1.4` on all generated `.pdf` files."),
        ("Deterministic Validation Tests", "Validates rejection of missing required fields, invalid enum choices, and ungrounded ISO applicability exclusions."),
        ("Segregation of Duties Tests", "Verifies HTTP 403 Forbidden when author attempts self-review or self-approval."),
        ("Live Telemetry Diagnostics", "Active `/api/v1/diagnostics` endpoint benchmarking live SQLite response latency, NVIDIA NIM round-trip latency, and document rendering health.")
    ]
    for h, b in test_points:
        p = tf_p2.add_paragraph() if tf_p2.paragraphs[0].text else tf_p2.paragraphs[0]
        p.text = f"✓ {h}: "
        p.font.bold = True
        p.font.size = Pt(10)
        p.font.color.rgb = C_ACCENT_GREEN
        p2 = tf_p2.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(9)
        p2.font.color.rgb = C_TEXT_BODY
        p2.space_after = Pt(6)

    s14.notes_slide.notes_text_frame.text = (
        "Slide 14 presents our performance benchmarks and verification results.\n"
        "Migrating to NVIDIA NIM slashed document generation latency from ~45 seconds down to under 1 second—a 98% reduction.\n"
        "Single-section regeneration runs in just 250 milliseconds.\n"
        "Our test suite contains 89 automated tests verifying binary export headers, validation gates, "
        "and segregation of duties security rules."
    )

    # ==========================================
    # SLIDE 15: DEPLOYMENT, SCALABILITY & CONCLUSION
    # ==========================================
    s15 = prs.slides.add_slide(blank_layout)
    add_bg(s15)
    add_header(s15, "Production Deployment, Containerization & Roadmap")
    
    # 3 Summary Cards
    c_d1 = add_card(s15, Inches(0.8), Inches(1.6), Inches(3.6), Inches(5.3), "Docker Containerization")
    tb_d1 = s15.shapes.add_textbox(Inches(1.0), Inches(2.2), Inches(3.2), Inches(4.5))
    tf_d1 = tb_d1.text_frame
    tf_d1.word_wrap = True
    d1_items = [
        ("Multi-Stage Dockerfiles", "Minimal Python 3.13-slim image for FastAPI backend and Node 20-alpine for React/Vite frontend."),
        ("Docker Compose Orchestration", "Single-command container deployment (`docker compose up -d`) mounting data volumes for persistence."),
        ("Zero GPU Infrastructure Requirement", "Because inference is delegated to NVIDIA NIM hosted API, backend containers run efficiently on low-cost 2-vCPU / 4GB RAM instances.")
    ]
    for h, b in d1_items:
        p = tf_d1.add_paragraph() if tf_d1.paragraphs[0].text else tf_d1.paragraphs[0]
        p.text = f"• {h}: "
        p.font.bold = True
        p.font.size = Pt(10)
        p.font.color.rgb = C_ACCENT_CYAN
        p2 = tf_d1.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(9)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(8)

    c_d2 = add_card(s15, Inches(4.8), Inches(1.6), Inches(3.6), Inches(5.3), "Enterprise Scalability")
    tb_d2 = s15.shapes.add_textbox(Inches(5.0), Inches(2.2), Inches(3.2), Inches(4.5))
    tf_d2 = tb_d2.text_frame
    tf_d2.word_wrap = True
    d2_items = [
        ("Horizontal Pod Autoscaling", "FastAPI ASGI workers scale horizontally behind reverse proxies (Nginx / Traefik / AWS ALB)."),
        ("Managed PostgreSQL Backend", "One-line configuration switch via `DATABASE_URL` connects to managed AWS RDS or GCP Cloud SQL."),
        ("ChromaDB Client/Server Mode", "Seamless transition from local SQLite persistence to distributed ChromaDB cluster.")
    ]
    for h, b in d2_items:
        p = tf_d2.add_paragraph() if tf_d2.paragraphs[0].text else tf_d2.paragraphs[0]
        p.text = f"• {h}: "
        p.font.bold = True
        p.font.size = Pt(10)
        p.font.color.rgb = C_ACCENT_AMBER
        p2 = tf_d2.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(9)
        p2.font.color.rgb = C_TEXT_MUTED
        p2.space_after = Pt(8)

    c_d3 = add_card(s15, Inches(8.8), Inches(1.6), Inches(3.7), Inches(5.3), "Key Takeaways & Summary")
    tb_d3 = s15.shapes.add_textbox(Inches(9.0), Inches(2.2), Inches(3.3), Inches(4.5))
    tf_d3 = tb_d3.text_frame
    tf_d3.word_wrap = True
    d3_items = [
        ("Compliance First", "Deterministic quality gate guarantees ISO 13485 & 21 CFR Part 820 adherence before AI invocation."),
        ("Blazing Fast Cloud Inference", "Sub-second NVIDIA NIM hosted models replace heavy, brittle local daemons."),
        ("Complete Authoring Control", "In-place section editing and targeted single-section AI regeneration give users full flexibility."),
        ("Production Grade Artifacts", "Native `.docx` and `.pdf` binaries ready for regulatory audit submissions.")
    ]
    for h, b in d3_items:
        p = tf_d3.add_paragraph() if tf_d3.paragraphs[0].text else tf_d3.paragraphs[0]
        p.text = f"✓ {h}: "
        p.font.bold = True
        p.font.size = Pt(10)
        p.font.color.rgb = C_ACCENT_GREEN
        p2 = tf_d3.add_paragraph()
        p2.text = f"  {b}"
        p2.font.size = Pt(9)
        p2.font.color.rgb = C_TEXT_BODY
        p2.space_after = Pt(8)

    s15.notes_slide.notes_text_frame.text = (
        "To conclude, AiDocMaker represents a major leap forward in AI-assisted quality management documentation.\n"
        "By pairing deterministic rules validation with NVIDIA's hosted NIM microservices, we achieve sub-second generation, "
        "rock-solid regulatory compliance, and authentic document deliverables.\n"
        "The architecture is containerized, horizontally scalable, and thoroughly verified by 89 automated tests.\n"
        "Thank you, and I am now open to any technical questions."
    )

    prs.save(filename)
    print(f"Presentation saved successfully to {filename}")

if __name__ == "__main__":
    create_deck()
