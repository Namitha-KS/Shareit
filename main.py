import streamlit as st
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import re
import io
import time
import html

def clean_text_for_pdf(text):
    """Clean and prepare text for PDF generation."""
    text = html.unescape(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', "'")
    text = text.replace('\u2019', "'")
    text = text.replace('\u2018', "'")
    text = text.replace('\u201c', '"')
    text = text.replace('\u201d', '"')
    text = text.replace('```', '')
    text = re.sub(r'\n\s*\n', '\n', text)
    return text

def validate_chat_url(url):
    """Validate if the URL matches ChatGPT share link patterns."""
    patterns = [
        r'https://chat\.openai\.com/share/[a-zA-Z0-9-]+',
        r'https://chatgpt\.com/share/[a-zA-Z0-9-]+'
    ]
    
    for pattern in patterns:
        if re.match(pattern, url):
            if 'chatgpt.com' in url:
                return url.replace('chatgpt.com', 'chat.openai.com')
            return url
    return None

def create_pdf(conversation, include_metadata=True):
    """Create a PDF from the conversation content with optional metadata."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        spaceAfter=30
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#1a73e8'),
        spaceAfter=12
    )
    content_style = ParagraphStyle(
        'CustomContent',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=20,
        leading=14
    )
    metadata_style = ParagraphStyle(
        'MetadataStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.gray,
        spaceAfter=20
    )
    
    story = []
    story.append(Paragraph("ChatGPT Conversation", title_style))
    
    if include_metadata:
        metadata = f"Extracted on: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        story.append(Paragraph(metadata, metadata_style))
    
    story.append(Spacer(1, 12))
    
    try:
        for role, message, is_edited in conversation:
            clean_role = clean_text_for_pdf(role)
            clean_message = clean_text_for_pdf(message)
            
            if is_edited:
                clean_role += " (Edited)"
            
            story.append(Paragraph(clean_role, heading_style))
            
            paragraphs = clean_message.split('\n')
            for para in paragraphs:
                if para.strip():
                    story.append(Paragraph(para.strip(), content_style))
            
            story.append(Spacer(1, 12))
    
    except Exception as e:
        st.error(f"Error creating PDF: {str(e)}")
        return None
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def extract_conversation(url):
    """Extract conversation content from a shared ChatGPT URL."""
    try:
        with st.spinner("Initializing browser..."):
            options = uc.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-gpu')
            driver = uc.Chrome(options=options)
        
        with st.spinner("Loading conversation..."):
            driver.get(url)
            wait = WebDriverWait(driver, 20)
            conversation_elements = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[class*='markdown']"))
            )
            role_elements = driver.find_elements(By.CSS_SELECTOR, "div[class*='font-semibold']")
        
        conversation = []
        for idx, content in enumerate(conversation_elements):
            role = role_elements[idx].text if idx < len(role_elements) else "Unknown"
            message = content.text.strip()
            conversation.append([role, message, False])  # False indicates not edited
        
        return conversation
    
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        return None
    
    finally:
        if 'driver' in locals():
            driver.quit()

st.set_page_config(
    page_title="ChatGPT Conversation Extractor",
    page_icon="💬",
    layout="wide"
)

st.markdown("""
    <style>
        .stButton>button {
            width: 100%;
            margin-top: 1rem;
        }
        .main {
            padding: 2rem;
        }
        .edited-message {
            background-color: #f0f8ff;
            padding: 10px;
            border-radius: 5px;
        }
        .stTextArea>div>div>textarea {
            min-height: 100px;
        }
    </style>
""", unsafe_allow_html=True)

st.title("Make your GPT chats a PDF")
st.write("Enter a ChatGPT share link to extract, edit, and download the conversation as a PDF.")


if 'conversation' not in st.session_state:
    st.session_state.conversation = None

url = st.text_input("ChatGPT Share Link", placeholder="https://chat.openai.com/share/...")

if st.button("Extract Conversation"):
    if not url:
        st.warning("Please enter a ChatGPT share link.")
    else:
        validated_url = validate_chat_url(url)
        if not validated_url:
            st.error("Invalid ChatGPT share URL format. Please check the URL and try again.")
        else:
            st.session_state.conversation = extract_conversation(validated_url)
            
            if st.session_state.conversation:
                # Create original PDF download button
                pdf_buffer = create_pdf(st.session_state.conversation)
                if pdf_buffer:
                    st.download_button(
                        label="Download Original PDF",
                        data=pdf_buffer,
                        file_name="chatgpt_conversation_original.pdf",
                        mime="application/pdf"
                    )

if st.session_state.conversation:
    st.subheader("Edit Conversation")
    edited_conversation = []
    
    for idx, (role, message, is_edited) in enumerate(st.session_state.conversation):
        col1, col2 = st.columns([1, 4])
        
        with col1:
            edited_role = st.text_input(f"Prompt {idx+1}", value=role, key=f"role_{idx}")
        
        with col2:
            edited_message = st.text_area(f"Response {idx+1}", value=message, key=f"message_{idx}")
        
        is_edited = (edited_role != role) or (edited_message != message)
        edited_conversation.append([edited_role, edited_message, is_edited])
        
        st.markdown("---")
    

    st.session_state.conversation = edited_conversation
    

    pdf_buffer = create_pdf(edited_conversation)
    if pdf_buffer:
        st.download_button(
            label="Download Edited PDF",
            data=pdf_buffer,
            file_name="chatgpt_conversation_edited.pdf",
            mime="application/pdf"
<<<<<<< HEAD
        )
=======
        )
>>>>>>> 3100cccc9e442e6d40e9162d00834297c20b1489
