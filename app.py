import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from urllib.parse import urlparse
import re

st.set_page_config(page_title="Internal link Analysis Dashboard", layout="wide")


def load_data():
    return pd.read_csv('lumar_internal_links.csv')


@st.cache_data
def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    # Extract subdomain from target_url
    def get_subdomain(url):
        try:
            parsed = urlparse(url)
            domain_parts = parsed.netloc.split('.')
            if len(domain_parts) > 2:
                return domain_parts[0]
            return 'www'
        except:
            return 'unknown'

    df = df.copy()
    df['subdomain'] = df['target_url'].apply(get_subdomain)

    # Create anchor variability groups
    def categorise_anchor_count(count):
        if pd.isna(count):
            return 'Unknown'
        try:
            count = int(count)
        except:
            return 'Unknown'
        if count <= 3:
            return '1-3'
        elif count <= 5:
            return '4-5'
        elif count <= 8:
            return '6-8'
        else:
            return '8+'

    df['anchor_variability'] = df['unique_anchor_text_count'].apply(categorise_anchor_count)

    # Extract URL components (first two path segments)
    def get_url_components(url):
        try:
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            if not path:
                return None, None
            parts = path.split('/')
            component1 = f"/{parts[0]}/" if len(parts) > 0 else None
            component2 = f"/{parts[1]}/" if len(parts) > 1 else None
            return component1, component2
        except:
            return None, None

    df[['url_component_1', 'url_component_2']] = df['target_url'].apply(
        lambda x: pd.Series(get_url_components(x))
    )

    return df


@st.cache_data
def expand_anchor_texts(df: pd.DataFrame) -> pd.DataFrame:
    """Expand anchor texts into separate rows for search functionality"""
    expanded_rows = []

    for idx, row in df.iterrows():
        target_url = row['target_url']
        anchor_texts = str(row['anchor_texts'])
        found_at = str(row['found_at'])

        # Split anchor texts and found_at by semicolon
        anchors = [a.strip() for a in anchor_texts.split(';') if a.strip()]
        found_ats = [f.strip() for f in found_at.split(';') if f.strip()]

        # Match anchors with found_at URLs
        for i, anchor in enumerate(anchors):
            found_url = found_ats[i] if i < len(found_ats) else ''
            expanded_rows.append({
                'target_url': target_url,
                'anchor_text': anchor,
                'found_at': found_url
            })

    return pd.DataFrame(expanded_rows)


# Title
st.title("🔗 Internal link Analysis Dashboard")

df = load_data()
df = prepare_data(df)
df_expanded = expand_anchor_texts(df)

# Sidebar filters
st.sidebar.header("Filters")

# Subdomain filter
subdomains = ['ALL'] + sorted(df['subdomain'].unique().tolist())
selected_subdomain = st.sidebar.selectbox("Select Subdomain", subdomains)

# Filter data
if selected_subdomain != 'ALL':
    filtered_df = df[df['subdomain'] == selected_subdomain].copy()
else:
    filtered_df = df.copy()

# Tabs
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "🔍 Search", "⚠️ Missing Anchor Text Report"])

with tab1:
    st.header(f"Analysis for: {selected_subdomain}")
    
    # Anchor Variability Chart
    st.subheader("Anchor Variability Distribution")
    
    # Order for the groups
    group_order = ['1-3', '4-5', '6-8', '8+']
    anchor_counts = filtered_df['anchor_variability'].value_counts()
    anchor_counts = anchor_counts.reindex(group_order, fill_value=0)
    
    fig = px.bar(
        x=anchor_counts.index,
        y=anchor_counts.values,
        labels={'x': 'Anchor Variability', 'y': 'Number of URLs'},
        title='URLs by Anchor Text Variability',
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    colors = ['#66c2a5', '#fc8d62', '#8da0cb', '#e78ac3']  # Set2 colours
    fig.update_traces(marker_color=colors, width=0.4)
    fig.update_layout(showlegend=False, xaxis_title='Anchor Variability', yaxis_title='Count', bargap=0.2)
    
    selected_bar = st.plotly_chart(fig, width='stretch', key="main_chart")
    
    # Selection box for bar chart
    selected_group = st.selectbox(
        "Select Anchor Variability Group to Analyse",
        group_order,
        key='group_select'
    )
    
    if selected_group:
        selected_data = filtered_df[filtered_df['anchor_variability'] == selected_group]
        
        if len(selected_data) > 0:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("URL Component 1 Analysis")
                component1_counts = selected_data['url_component_1'].value_counts()
                total = len(selected_data)
                component1_pct = (component1_counts / total * 100).round(2)
                
                component1_df = pd.DataFrame({
                    'Component': component1_counts.index,
                    'Count': component1_counts.values,
                    'Percentage': component1_pct.values
                })
                component1_df['Percentage'] = component1_df['Percentage'].apply(lambda x: f"{x}%")
                
                st.dataframe(component1_df, width='stretch', hide_index=True)
            
            with col2:
                st.subheader("URL Component 2 Analysis")
                component2_data = selected_data[selected_data['url_component_2'].notna()]
                
                if len(component2_data) > 0:
                    component2_counts = component2_data['url_component_2'].value_counts()
                    component2_total = len(component2_data)
                    component2_pct = (component2_counts / component2_total * 100).round(2)
                    
                    component2_df = pd.DataFrame({
                        'Component': component2_counts.index,
                        'Count': component2_counts.values,
                        'Percentage': component2_pct.values
                    })
                    component2_df['Percentage'] = component2_df['Percentage'].apply(lambda x: f"{x}%")
                    
                    st.dataframe(component2_df, width='stretch', hide_index=True)
                else:
                    st.info("No second-level URL components found for this selection.")
        else:
            st.info(f"No data available for the {selected_group} group.")

with tab2:
    st.header("Search URLs")
    
    search_term = st.text_input("Search in target URL (contains)", "")
    
    if search_term:
        # Filter expanded dataframe
        search_results = df_expanded[
            df_expanded['target_url'].str.contains(search_term, case=False, na=False)
        ].copy()
        
        if len(search_results) > 0:
            st.success(f"Found {len(search_results)} results")
            st.dataframe(
                search_results[['target_url', 'anchor_text', 'found_at']],
                width='stretch',
                hide_index=True
            )
        else:
            st.warning("No results found")
    else:
        st.info("Enter a search term to find matching URLs")

with tab3:
    st.header("Missing Anchor Text Report")
    st.write("Shows URLs where anchor texts contain '| (' pattern")
    
    # Filter for missing anchor texts
    missing_anchor_df = df[
        df['anchor_texts'].astype(str).str.contains(r'\|\s*\(', regex=True, na=False)
    ].copy()
    
    if len(missing_anchor_df) > 0:
        st.warning(f"Found {len(missing_anchor_df)} URLs with missing anchor text patterns")
        
        display_df = missing_anchor_df[[
            'target_url', 'anchor_texts', 'unique_anchor_text_count', 
            'total_inlinks', 'found_at'
        ]].copy()
        
        st.dataframe(display_df, width='stretch', hide_index=True)
        
        # Download button
        csv = display_df.to_csv(index=False)
        st.download_button(
            label="Download Missing Anchor Text Report",
            data=csv,
            file_name="missing_anchor_text_report.csv",
            mime="text/csv"
        )
    else:
        st.success("No missing anchor text patterns found!")