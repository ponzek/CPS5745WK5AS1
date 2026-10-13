import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from database import connect
st.set_page_config(page_title='CPS5745 | Geographic ZIP Explorer',layout='wide')
st.title('Geographic ZIP Explorer')
st.caption('Fall 2026 · ZIP-level population, density and timezone · PostgreSQL → Plotly')
@st.cache_data(ttl=120)
def states_list():
    with connect() as c:
        return pd.read_sql_query('SELECT DISTINCT state_id FROM lab.uszips WHERE state_id IS NOT NULL ORDER BY state_id',c).state_id.tolist()
@st.cache_data(ttl=120)
def fetch_rows(states):
    if not states: return pd.DataFrame()
    from psycopg2 import sql
    with connect() as c:
        return pd.read_sql_query('''SELECT zip,state_id,city,county_fips,county_name,population,density,timezone
        FROM lab.uszips WHERE state_id = ANY(%s)''',c,params=(list(states),))
@st.cache_data(ttl=120)
def source_info():
    with connect() as c:
        with c.cursor() as cur:
            cur.execute('SELECT csv_sha256,row_count,imported_at FROM lab.import_manifest WHERE id=1')
            return cur.fetchone()
def mode(v):
    s=v.dropna().value_counts();return sorted(s[s==s.max()].index)[0] if len(s) else None
def summarize(rows,level):
    a=rows.copy()
    if level=='State':
        a['group_id']=a.state_id;a['geography']=a.state_id
    elif level=='County':
        a['group_id']=a.county_fips.fillna('Unassigned')
        a['geography']=a.county_name.fillna('Unassigned')+' ('+a.group_id+')'
    else:
        a['group_id']=a.state_id.fillna('')+' | '+a.city.fillna('Unassigned')
        a['geography']=a.city.fillna('Unassigned')+', '+a.state_id.fillna('')
    s=a.groupby('group_id',dropna=False).agg(geography=('geography','first'),zip_count=('zip','size'),population_n=('population','count'),population_sum=('population',lambda x:x.sum(min_count=1)),population_mean=('population','mean'),density_n=('density','count'),density_mean=('density','mean'),density_median=('density','median'),timezone_mode=('timezone',mode),timezone_count=('timezone','nunique')).reset_index()
    return a,s
try:
    sha,nrows,imported=source_info()
    all_states=states_list()
except Exception as e:
    st.error('PostgreSQL is unavailable or has not been imported. Run setup, load, and verify commands first.');st.code(str(e));st.stop()
st.caption(f'**Source:** SimpleMaps Basic v1.95.1 · **Database:** cps5745_lab / lab.uszips · **Imported rows:** {nrows:,} · **Imported at:** {imported} · **CSV SHA-256:** `{sha}`')
with st.sidebar:
    st.header('Filters · PostgreSQL')
    selected_states=st.multiselect('States / territories',all_states,default=all_states)
    level=st.selectbox('Group ZIP records by',['County','State','City'])
    minimum=st.number_input('Minimum ZIP records per group',min_value=1,max_value=1000,value=1)
    top_n=st.slider('Top N for bar and box only',1,30,10)
    st.caption('Top N changes displayed groups, not the selected ZIP count or scatter data.')
if not selected_states:
    st.info('No states selected. Select at least one state to display the charts.');st.stop()
try: rows=fetch_rows(tuple(sorted(selected_states)))
except Exception as e: st.error(f'Database query failed: {e}');st.stop()
if rows.empty: st.info('No matching ZIP records.');st.stop()
keyed,all_summary=summarize(rows,level)
summary=all_summary.loc[all_summary.zip_count>=minimum].copy()
keyed=keyed.loc[keyed.group_id.isin(summary.group_id)].copy()
a,b,c=st.columns(3)
a.metric('Selected ZIP records',f'{len(keyed):,}')
b.metric('Eligible geographic groups',f'{len(summary):,}')
c.metric('Observed population sum',f'{keyed.population.sum(min_count=1):,.0f}' if keyed.population.notna().any() else 'Missing')
st.caption(f'Population observed: {keyed.population.count():,}/{len(keyed):,} · Density observed: {keyed.density.count():,}/{len(keyed):,} · Source rows before minimum-size threshold: {len(rows):,}')
if keyed.empty: st.info('No geographic groups meet this minimum ZIP count. Reduce the minimum or broaden the states.');st.stop()
ranked=summary.dropna(subset=['population_sum']).sort_values(['population_sum','geography'],ascending=[False,True]).head(top_n)
st.subheader('1 · Assigned-ZIP population by geographic group')
if not ranked.empty:
    fig=px.bar(ranked.iloc[::-1],x='population_sum',y='geography',orientation='h',hover_data=['zip_count','population_n'],labels={'population_sum':'Sum of observed ZIP population estimates','geography':'Geographic group'})
    fig.update_xaxes(rangemode='tozero');st.plotly_chart(fig,use_container_width=True)
st.caption('One bar = sum of available assigned-ZIP population estimates. Not an independently verified official county total.')
st.subheader('2 · Mean ZIP density versus mean ZIP population')
scatter=summary.dropna(subset=['density_mean','population_mean']).copy()
if len(scatter):
    fig=px.scatter(scatter,x='density_mean',y='population_mean',color='timezone_mode',hover_name='geography',hover_data=['zip_count','population_n','density_n','timezone_count'],labels={'density_mean':'Mean ZIP density (people/km²)','population_mean':'Mean ZIP population','timezone_mode':'Most frequent timezone'})
    st.plotly_chart(fig,use_container_width=True)
else: st.info('No groups with both observed means.')
st.caption('One point per eligible group; categorical timezone by number of ZIP records. Scatter includes all eligible groups, unaffected by Top N.')
st.subheader('3 · Variation of observed ZIP densities')
box_data=keyed.loc[keyed.group_id.isin(ranked.group_id) & keyed.density.notna()].copy()
if not box_data.empty:
    box_data['geography']=pd.Categorical(box_data.geography,categories=ranked.geography.iloc[::-1].tolist(),ordered=True)
    fig=px.box(box_data,x='density',y='geography',orientation='h',points='outliers',labels={'density':'ZIP density (people/km²)','geography':'Geographic group'})
    fig.update_traces(quartilemethod='linear');st.plotly_chart(fig,use_container_width=True)
else: st.info('No observed density values among top groups.')
st.caption('Boxes summarize observed ZIP-level density distributions; whiskers use the 1.5×IQR convention. Top N affects only displayed box groups.')
with st.expander('Source rows, summary, and downloads'):
    st.dataframe(summary,use_container_width=True)
    st.download_button('Download geographic summary',summary.to_csv(index=False).encode(),file_name='geography_summary.csv',mime='text/csv')
    st.dataframe(keyed,use_container_width=True)
    st.download_button('Download selected ZIP records',keyed.to_csv(index=False).encode(),file_name='selected_zip_rows.csv',mime='text/csv')
