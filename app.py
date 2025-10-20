import os
import streamlit as st
import pandas as pd
from pathlib import Path
# Import the template from config file
from config import SYSTEM_PROMPT_TEMPLATE
import requests 

POWER_BI_IFRAME_URL = "https://powerbiembeddedexample-gsffd0h3fxe2hmgm.southeastasia-01.azure-api.net/"

# --- Loads and caches CSV data ---
@st.cache_data
def load_data_as_markdown():
    """Loads the reference data CSV and returns it as a markdown string."""
    try:
        df = pd.read_csv("reference_sample_data.csv")
        return df.to_markdown(index=False)
    except FileNotFoundError:
        st.error("Error: The data file (reference_sample_data.csv) was not found.")
        return None
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

# Import Streamlit components
try:
    import streamlit.components.v1 as components
except Exception:
    components = None # Will be handled by fallback


def call_hackathon_chat(messages):
    """
    Call the custom PSA Code Sprint Hackathon API endpoint.
    """
    api_key = st.session_state.get('hackathon_api_key') or os.environ.get('HACKATHON_API_KEY')
    if not api_key:
        raise RuntimeError("Hackathon API key not configured. Set HACKATHON_API_KEY or paste it in the UI.")

    ENDPOINT_URL = "https://psacodesprint2025.azure-api.net/openai/deployments/gpt-4.1-nano/chat/completions?api-version=2025-01-01-preview"
    
    headers = { "Content-Type": "application/json", "api-key": api_key }
    body = {
        "messages": messages,
        "model": "gpt-4.1-nano",
        "max_tokens": 800 
    }

    try:
        response = requests.post(ENDPOINT_URL, headers=headers, json=body)
        response.raise_for_status() 
        response_json = response.json()
        return response_json['choices'][0]['message']['content']

    except requests.exceptions.HTTPError as http_err:
        error_details = f"HTTP error occurred: {http_err}."
        try:
            error_body = http_err.response.json()
            error_message = error_body.get('error', {}).get('message', 'No error message provided.')
            error_details += f" Server response: {error_message}"
        except Exception:
            error_details += f" Server response: {http_err.response.text}"
        raise RuntimeError(error_details)
    except KeyError:
        raise RuntimeError(f"Failed to parse AI response. Received: {response_json}")
    except Exception as e:
        raise RuntimeError(f"Hackathon API request failed: {e}") from e

# --- Power BI Config ---
PBI_CLIENT_ID = os.environ.get("PBI_CLIENT_ID")
PBI_CLIENT_SECRET = os.environ.get("PBI_CLIENT_SECRET")
PBI_TENANT_ID = os.environ.get("PBI_TENANT_ID")
PBI_WORKSPACE_ID = os.environ.get("PBI_WORKSPACE_ID")
PBI_REPORT_ID = os.environ.get("PBI_REPORT_ID")
PBI_EMBED_TOKEN = os.environ.get("PBI_EMBED_TOKEN")


# --- APP LAYOUT ---

st.title("VoyageAnalyst 🚢")
st.caption("An AI-powered analyst for actionable insights on global operations, efficiency, and sustainability.")


st.header("Global Insights Dashboard")
if PBI_CLIENT_ID and PBI_CLIENT_SECRET and PBI_TENANT_ID and PBI_WORKSPACE_ID and PBI_REPORT_ID:
    if 'pbi_embed_info' not in st.session_state:
        st.write("Embedding Power BI report (fetching new token)...")
        def get_embed_info(client_id, client_secret, tenant_id, group_id, report_id):
            try:
                from msal import ConfidentialClientApplication
                import requests
            except Exception as e:
                raise RuntimeError("Missing dependencies: `pip install msal requests`") from e
            
            # --- FIXED URL ---
            authority = f"https://login.microsoftonline.com/{tenant_id}"
            app = ConfidentialClientApplication(client_id, authority=authority, client_credential=client_secret)
            
            # --- FIXED URL ---
            result = app.acquire_token_for_client(scopes=["https://analysis.windows.net/powerbi/api/.default"])
            if "access_token" not in result:
                raise RuntimeError(f"Failed to acquire AAD token: {result}")
            
            access_token = result["access_token"]
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # --- FIXED URL ---
            report_resp = requests.get(f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/reports/{report_id}", headers=headers)
            report_resp.raise_for_status()
            report_json = report_resp.json()
            embed_url = report_json.get("embedUrl")
            
            token_body = {"accessLevel": "View"}
            
            # --- FIXED URL ---
            token_resp = requests.post(f"https://api.powerbi.com/v1.0/myorg/groups/{group_id}/reports/{report_id}/GenerateToken", headers={**headers, "Content-Type": "application/json"}, json=token_body)
            token_resp.raise_for_status()
            token_json = token_resp.json()
            
            st.session_state.pbi_embed_info = { 
                "embedUrl": embed_url, 
                "embedToken": token_json.get("token"),
                "expiration": token_json.get("expiration"), 
                "reportId": report_id 
            }

        if PBI_EMBED_TOKEN:
            # --- FIXED URL ---
            embed_url = f"https://app.powerbi.com/reportEmbed?reportId={PBI_REPORT_ID}&groupId={PBI_WORKSPACE_ID}&autoAuth=true&ctid={PBI_TENANT_ID}"
            st.session_state.pbi_embed_info = { "embedUrl": embed_url, "embedToken": PBI_EMBED_TOKEN, "reportId": PBI_REPORT_ID }
        else:
            try:
                get_embed_info(PBI_CLIENT_ID, PBI_CLIENT_SECRET, PBI_TENANT_ID, PBI_WORKSPACE_ID, PBI_REPORT_ID)
            except Exception as e:
                st.error(f"Could not generate embed token: {e}")
                st.session_state.pbi_embed_info = None
    
    info = st.session_state.get('pbi_embed_info')
    if info and components is not None:
        embed_html = f"""
        <div id='reportContainer' style='width:100%;height:650px;'></div>
        
        <script src='https://cdn.jsdelivr.net/npm/powerbi-client/dist/powerbi.js'></script>
        <script>
            const embedConfig = {{
            type: 'report',
            tokenType: window['powerbi-client'].models.TokenType.Embed,
            accessToken: '{info['embedToken']}',
            embedUrl: '{info['embedUrl']}',
            id: '{info['reportId']}',
            settings: {{ panes: {{ filters: {{ visible: false }} }} }}
            }};
            const reportContainer = document.getElementById('reportContainer');
            if (!reportContainer.powerbi) {{
                window.powerbi && window.powerbi.embed(reportContainer, embedConfig);
                reportContainer.powerbi = true;
            }}
        </script>
        """
        components.html(embed_html, height=650)
    else:
        st.info("Falling back to example dashboard iframe.")
        components.iframe(POWER_BI_IFRAME_URL, height=650)
else:
    st.info("Using example dashboard (no Power BI service principal configured).")
    components.iframe(POWER_BI_IFRAME_URL, height=650, scrolling=True) 


st.header("AI Analyst")

if 'hackathon_api_key' not in st.session_state:
    st.session_state.hackathon_api_key = os.environ.get('HACKATHON_API_KEY', '')
if not st.session_state.hackathon_api_key:
    key_input = st.text_input("Hackathon API key (optional, or set HACKATHON_API_KEY)", type="password")
    if key_input:
        st.session_state.hackathon_api_key = key_input

data_md = load_data_as_markdown()

if data_md is None:
    st.error("Data could not be loaded. AI Analyst is offline.")
else:
    final_system_prompt = SYSTEM_PROMPT_TEMPLATE.format(data_context=data_md)

    if 'messages' not in st.session_state:
        st.session_state.messages = []
        # This adds the BIG prompt (with data) just once
        st.session_state.messages.append({"role": "system", "content": final_system_prompt})

    # Render prior messages
    for msg in st.session_state.messages:
        if msg['role'] == 'user':
            with st.chat_message('user'):
                st.markdown(msg['content'])
        elif msg['role'] == 'assistant':
            with st.chat_message('ai'):
                st.markdown(msg['content'])

    # Chat input
    user_input = st.chat_input("Ask me about the dashboard...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message('user'):
            st.markdown(user_input)
        
        CONTEXT_WINDOW_SIZE = 6 

        if len(st.session_state.messages) <= 2: # i.e., [system, user]
            to_send = st.session_state.messages.copy()
        else:
            all_user_and_assistant_messages = st.session_state.messages[1:]
            windowed_user_and_assistant_messages = all_user_and_assistant_messages[-CONTEXT_WINDOW_SIZE:]
            to_send = [
                st.session_state.messages[0] # The system prompt
            ] + windowed_user_and_assistant_messages # The recent N messages
        
        try:
            with st.spinner('Thinking...'):
                assistant_text = call_hackathon_chat(to_send)
        except Exception as e:
            st.error(f"API request failed: {e}")
            assistant_text = "Sorry — I couldn't reach the AI service. Check logs or your API key."

        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
        with st.chat_message('ai'):
            st.markdown(assistant_text)