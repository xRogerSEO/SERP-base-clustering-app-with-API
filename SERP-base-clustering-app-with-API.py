import streamlit as st
import pandas as pd
import requests
import json
import time
import plotly.express as px

st.title('SERP Based Clustering APP w/API')

# Function to clean Excel data
def clean_excel_data(file_path):
    terms_df = pd.read_excel(file_path)
    new_df = (
        terms_df[['Keyword', 'Volume']]
        .rename(columns={'Keyword': 'query'})
    )
    new_df['Volume'] = new_df['Volume'].fillna(0).astype(int)
    new_df['query'] = new_df['query'].astype(str).str.replace('[^a-zA-Z0-9 ]', '', regex=True)
    new_df['query_length'] = new_df['query'].apply(len)
    new_df = new_df[new_df['query_length'] > 3]
    new_df = new_df.drop(columns=['query_length'])
    return new_df

# Function to start batch
def start_batch(batch_id, api_key):
    params = {'api_key': str(api_key)}
    api_result = requests.get(f'https://api.valueserp.com/batches/{batch_id}/start', params=params)
    api_response = api_result.json()
    return api_response

# Function to get search results
def get_search_results(json_url):
    response = requests.get(json_url)
    if response.status_code == 200:
        response_json = response.json()
        return response_json
    else:
        st.error(f"Error: {response.status_code} - {response.text}")

# Function to clean search results
def clean_search_results(result_set):
    query_list = []
    links_list = []

    for result_link in result_set:
        response_json = get_search_results(result_link)

        for each in response_json:
            query = each['result']['search_parameters']['q']
            query_list.append(query)

            try:
                links = [link['link'] for link in each['result']['organic_results']]
                links_list.append(links)
            except KeyError:
                links_list.append([])
                st.warning(f"KeyError: 'organic_results' not found in result for query: {query}")

    data = {'query': query_list, 'links': links_list}
    serp_df = pd.DataFrame(data)

    return serp_df

# Function to retrieve clusters from API
def get_clusters_from_api(serp_df, common_num=4):
    url = 'https://us-central1-searchblend.cloudfunctions.net/serp-based-clustering'
    headers = {'Content-Type': 'application/json'}

    post_data = {
        "serp_df": serp_df.to_dict(),
        "common_num": common_num
    }

    json_data = json.dumps(post_data)

    response = requests.post(url, data=json_data, headers=headers)

    if response.status_code == 200:
        clusters_df_cloud = pd.DataFrame(json.loads(response.text))
        return clusters_df_cloud
    else:
        st.error("Error:", response.status_code)
        return None

# Streamlit App
def main():
    st.title("GSC Queries Race Chart Visualization")

    # File upload section
    uploaded_file = st.file_uploader("Upload CSV file", type=['csv', 'xlsx'])

    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)

        st.write("Data Sample:")
        st.write(df.head())

        # Clean data
        cleaned_df = clean_excel_data(uploaded_file)

        st.write("Cleaned Data Sample:")
        st.write(cleaned_df.head())

        # API Key input
        api_key = st.text_input("Enter your ValueSERP API key:")

        # Batch Name
        batch_name = st.text_input("Enter batch name:")

        # Search Location
        search_location = st.text_input("Enter search location (e.g., Chicago, Illinois, USA):")

        # Language & Google Domain
        gl = st.text_input("Enter Google language code (e.g., en):")
        hl = st.text_input("Enter Google search language (e.g., us):")
        google_domain = st.text_input("Enter Google domain (e.g., google.com):")

        # Start processing
        if st.button("Start Processing"):
            batch_id = create_batch(batch_name, api_key)
            st.write("Batch ID:", batch_id)
            time.sleep(1)

            add_search_queries(batch_id, cleaned_df, api_key, search_location, gl, hl, google_domain)
            st.write('Added Search Queries to the ValueSERP Batch')
            time.sleep(1)

            start_batch(batch_id, api_key)
            st.write('Started the ValueSERP Batch')
            st.write('Waiting for SERP Results')

            result_set = get_result_set(batch_id, api_key)
            st.write('SERP Scraping Successful.')

            cleaned_results = clean_search_results(result_set)
            st.write('Cleaned Results')

            merged_df = pd.merge(cleaned_df, cleaned_results, how='left', on='query')
            merged_df = merged_df.rename(columns={'query': 'Keyword', 'impressions': 'Volume', 'links': 'URLs'})

            clusters_df_cloud = get_clusters_from_api(merged_df)

            if clusters_df_cloud is not None:
                st.write("Clusters Data:")
                st.write(clusters_df_cloud.head())

                # Visualization
                st.write("Visualization:")
                fig = px.treemap(clusters_df_cloud[clusters_df_cloud['Number of Keywords in Cluster'] > 3],
                                 path=['Cluster Name', 'Keyword'])
                st.plotly_chart(fig)

if __name__ == '__main__':
    main()
