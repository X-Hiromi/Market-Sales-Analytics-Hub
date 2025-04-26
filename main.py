import streamlit as st
import plotly.express as px
import pandas as pd
import duckdb
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from io import BytesIO
import base64
from datetime import datetime
import warnings
import random


warnings.filterwarnings('ignore')

# Page Configuration
st.set_page_config(page_title="Dynamic EDA Report", page_icon=":bar_chart:", layout="wide")

# Title
st.title("📊 Market Sales Analytics Hub")
st.markdown('<style>div.block-container{padding-top:4rem;}</style>', unsafe_allow_html=True)

# File Uploader
fl = st.file_uploader(":file_folder: Upload a CSV file", type=["csv"])

if fl is not None:
    # Data Reading
    df = pd.read_csv(fl)

    # Column Type Identification
    numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
    categorical_columns = df.select_dtypes(exclude=['number']).columns.tolist()
    date_columns = df.select_dtypes(include=['datetime64[ns]']).columns.tolist()
    all_columns = df.columns.tolist()

    # Column Selection
    date_column_selection = st.selectbox("Select Date Column (for time series)", [None] + categorical_columns + date_columns)
    date_column = None
    if date_column_selection:
        date_column = date_column_selection
        if date_column in categorical_columns and date_column not in date_columns:
            try:
                df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
                date_columns.append(date_column)
            except Exception as e:
                st.warning(f"Could not convert selected Date Column to datetime: {e}")
                date_column = None

    category_column = st.selectbox("Select Category Column", [None] + categorical_columns)
    sales_column = st.selectbox("Select Sales Column", [None] + numeric_columns)

    if sales_column:
        df[sales_column] = pd.to_numeric(df[sales_column], errors='coerce').fillna(0)

    # Date Range Selection
    if date_column:
        startDate = df[date_column].min()
        endDate = df[date_column].max()
        col1, col2 = st.columns((2))
        with col1:
            date1 = st.date_input("Start Date", startDate)
        with col2:
            date2 = st.date_input("End Date", endDate)
        df = df[(df[date_column].dt.date >= date1) & (df[date_column].dt.date <= date2)].copy()

    # Sidebar Filters
    st.sidebar.header("Choose your filter: ")
    filters = {}
    for col in categorical_columns:
        unique_values = df[col].unique()
        selected_values = st.sidebar.multiselect(f"Pick your {col}", unique_values)
        if selected_values:
            filters[col] = selected_values

    # Data Filtering
    filtered_df = df.copy()
    for col, values in filters.items():
        filtered_df = filtered_df[filtered_df[col].isin(values)]

    # DuckDB Connection
    con = duckdb.connect(database=':memory:', read_only=False)
    con.register('sales_data', filtered_df)

    # KPI Calculations
    col1, col2, col3, col4 = st.columns(4)
    kpi_data = {}
    if sales_column:
        kpi_data['total_sales'] = con.execute(f'SELECT SUM("{sales_column}") FROM sales_data').fetchone()[0] or 0
    kpi_data['total_transactions'] = con.execute("SELECT COUNT(*) FROM sales_data").fetchone()[0] or 0
    if category_column:
        kpi_data['unique_categories'] = con.execute(f'SELECT COUNT(DISTINCT "{category_column}") FROM sales_data').fetchone()[0] or 0
    if date_column:
        kpi_data['date_range'] = con.execute(f'SELECT MIN("{date_column}"), MAX("{date_column}") FROM sales_data').fetchone()

    # KPI Display
    with col1:
        if 'total_sales' in kpi_data:
            st.markdown(f'<div class="metric-card">📊 Total Sales<br><b>${kpi_data["total_sales"]:,.2f}</b></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card">📂 Total Transactions<br><b>{kpi_data["total_transactions"]}</b></div>', unsafe_allow_html=True)
    with col3:
        if 'unique_categories' in kpi_data:
            st.markdown(f'<div class="metric-card">🛍️ Unique Categories<br><b>{kpi_data["unique_categories"]}</b></div>', unsafe_allow_html=True)
    with col4:
        if 'date_range' in kpi_data and kpi_data['date_range'] and kpi_data['date_range'][0] and kpi_data['date_range'][1]:
            st.markdown(f'<div class="metric-card">📆 Date Range<br><b>{kpi_data["date_range"][0].strftime("%Y-%m-%d")} - {kpi_data["date_range"][1].strftime("%Y-%m-%d")}</b></div>', unsafe_allow_html=True)

    # Tabs for Analysis
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📜 SQL Query", "📋 Data Summary", "📊 Dynamic Report", "⬇️ Download Reports", "Storyteller", "What-If Analysis", "Trivia Game"])

    # Tab 1: SQL Query
    with tab1:
        st.subheader("Run DuckDB SQL Query")
        sql_query = st.text_area("Enter your DuckDB SQL query:", "SELECT * FROM sales_data LIMIT 10;")
        if st.button("Run SQL"):
            try:
                result_df = con.execute(sql_query).df()
                st.dataframe(result_df)
            except Exception as e:
                st.error(f"❌ Error: {e}")

    # Tab 2: Data Summary
    with tab2:
        st.subheader("📋 Data Summary")
        st.write(filtered_df.describe())

    # Tab 3: Dynamic Report
    with tab3:
        st.subheader("📊 Dynamic Exploratory Data Analysis Report")
        st.write("Here's a dynamically generated report based on your data. The system will choose relevant chart types.")
        cols = st.columns(3)
        plot_counter = 0

        for i in range(min(9, len(numeric_columns) + len(categorical_columns))): # Limit to 9 charts.
            with cols[plot_counter % 3]:
                chart_type = None
                fig = None

                if len(numeric_columns) >= 2 and i % 7 == 0:
                    x_col = numeric_columns[i % len(numeric_columns)]
                    y_col = numeric_columns[(i + 1) % len(numeric_columns)]
                    chart_type = "Scatter Plot"
                    try:
                        fig = px.scatter(filtered_df, x=x_col, y=y_col, title=f"{y_col} vs {x_col}")
                        st.plotly_chart(fig)
                        plot_counter += 1
                        continue
                    except Exception as e:
                        st.warning(f"Could not create {chart_type} ({x_col}, {y_col}): {e}")
                elif categorical_columns and i % 7 == 1 :
                    cat_col = categorical_columns[i % len(categorical_columns)]
                    chart_type = "Pie Chart"
                    try:
                        fig = px.pie(filtered_df, names=cat_col, title=f"Distribution of {cat_col}")
                        st.plotly_chart(fig)
                        plot_counter += 1
                        continue
                    except Exception as e:
                        st.warning(f"Could not create {chart_type} ({cat_col}): {e}")
                elif categorical_columns and sales_column and i % 7 == 2 :
                    cat_col = categorical_columns[i % len(categorical_columns)]
                    chart_type = "Bar Chart (Mean Sales)"
                    try:
                        grouped = filtered_df.groupby(cat_col)[sales_column].mean().reset_index()
                        fig = px.bar(grouped, x=cat_col, y=sales_column, title=f"Avg Sales by {cat_col}", color=cat_col)
                        st.plotly_chart(fig)
                        plot_counter += 1
                        continue
                    except Exception as e:
                        st.warning(f"Could not create {chart_type} ({cat_col}): {e}")
                elif numeric_columns and i % 7 == 3 :
                    num_col = numeric_columns[i % len(numeric_columns)]
                    chart_type = "Histogram"
                    try:
                        fig = px.histogram(filtered_df, x=num_col, title=f"Distribution of {num_col}")
                        st.plotly_chart(fig)
                        plot_counter += 1
                        continue
                    except Exception as e:
                        st.warning(f"Could not create {chart_type} ({num_col}): {e}")
                elif categorical_columns and numeric_columns and i % 7 == 4:
                    cat_col = categorical_columns[i % len(categorical_columns)]
                    num_col = numeric_columns[i % len(numeric_columns)]
                    chart_type = "Box Plot"
                    try:
                        fig = px.box(filtered_df, x=cat_col, y=num_col, title=f"{num_col} distribution by {cat_col}", color=cat_col)
                        st.plotly_chart(fig)
                        plot_counter += 1
                        continue
                    except Exception as e:
                        st.warning(f"Could not create {chart_type} ({cat_col}, {num_col}): {e}")
                elif date_column and sales_column and i % 7 == 5 :
                    chart_type = "Time Series (Sales)"
                    try:
                        df_sorted = filtered_df.sort_values(by=date_column)
                        fig = px.line(df_sorted, x=date_column, y=sales_column, title=f"Sales Over Time")
                        st.plotly_chart(fig)
                        plot_counter += 1
                        continue
                    except Exception as e:
                        st.warning(f"Could not create {chart_type} ({date_column}, {sales_column}): {e}")
                elif len(numeric_columns) >= 2 and categorical_columns and i % 7 == 6 :
                    x_col = numeric_columns[i % len(numeric_columns)]
                    y_col = numeric_columns[(i + 1) % len(numeric_columns)]
                    color_col = categorical_columns[i % len(categorical_columns)]
                    chart_type = "Scatter Plot (with Category)"
                    try:
                        fig = px.scatter(filtered_df, x=x_col, y=y_col, color=color_col, title=f"{y_col} vs {x_col} by {color_col}")
                        st.plotly_chart(fig)
                        plot_counter += 1
                        continue
                    except Exception as e:
                        st.warning(f"Could not create {chart_type} ({x_col}, {y_col}, {color_col}): {e}")
                if chart_type is None:
                    st.info("No suitable data found to generate a dynamic chart.")

    # Tab 4: Download Reports
    with tab4:
        st.subheader("⬇️ Download Reports")
        report_type = st.selectbox("Select Report Type", ["CSV", "Summary Report (PDF)"])

    if report_type == "CSV":
        csv_buffer = io.StringIO()
        filtered_df.to_csv(csv_buffer, index=False)
        csv_string = csv_buffer.getvalue()
        csv_bytes = csv_string.encode('utf-8')
        st.download_button(
            label="Download Sales Report as CSV",
            data=csv_bytes,
            file_name="sales_report.csv",
            mime="text/csv",
        )
    elif report_type == "Summary Report (PDF)":
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()

        # Title
        title = Paragraph("Sales Summary Report", styles['h1'])
        story.append(title)
        story.append(Spacer(1, 12))

        # Generation Date
        date_para = Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
        story.append(date_para)
        story.append(Spacer(1, 24))

        # Data Summary Table
        summary_title = Paragraph("Data Summary:", styles['h2'])
        story.append(summary_title)
        summary_data = filtered_df.describe().round(2)
        summary_table_data = [summary_data.index.tolist()] + summary_data.values.tolist()
        summary_table = Table(summary_table_data)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 24))

        # KPI Table
        kpi_title = Paragraph("Key Performance Indicators:", styles['h2'])
        story.append(kpi_title)
        kpi_table_data = [["KPI", "Value"]]
        if 'total_sales' in kpi_data:
            kpi_table_data.append(["Total Sales", f"${kpi_data['total_sales']:,.2f}"])
        if 'total_transactions' in kpi_data:
            kpi_table_data.append(["Total Transactions", kpi_data['total_transactions']])
        if 'unique_categories' in kpi_data:
            kpi_table_data.append(["Unique Categories", kpi_data['unique_categories']])
        if 'date_range' in kpi_data and kpi_data['date_range'] and kpi_data['date_range'][0] and kpi_data['date_range'][1]:
            kpi_table_data.append(["Date Range", f"{kpi_data['date_range'][0].strftime('%Y-%m-%d')} - {kpi_data['date_range'][1].strftime('%Y-%m-%d')}"])
        elif 'date_range' in kpi_data:
            kpi_table_data.append(["Date Range", "N/A"])

        kpi_table = Table(kpi_table_data)
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(kpi_table)

        doc.build(story)
        buffer.seek(0)
        pdf_bytes = buffer.read()
        b64 = base64.b64encode(pdf_bytes).decode()
        href = f'<a href="data:application/pdf;base64,{b64}" download="sales_summary.pdf">Download Summary Report as PDF</a>'
        st.markdown(href, unsafe_allow_html=True)

    # Tab 5: Storyteller
    with tab5:
        st.subheader("Data Storyteller")
        st.write("Let's explore the data step by step.")

        if "story_step" not in st.session_state:
            st.session_state["story_step"] = 0

        story_steps = []
        if sales_column:
            story_steps.append({
                "question": f"What is the distribution of {sales_column}?",
                "visualization_function": lambda df, col: px.histogram(df, x=col, title=f"Distribution of {col}"),
                "column": sales_column
            })
        if category_column and sales_column:
            story_steps.append({
                "question": f"What is the average {sales_column} by {category_column}?",
                "visualization_function": lambda df, cat_col, sales_col: px.bar(df.groupby(cat_col)[sales_col].mean().reset_index(), x=cat_col, y=sales_col, title=f"Average {sales_col} by {cat_col}"),
                "columns": (category_column, sales_column)
            })
        if date_column and sales_column:
            story_steps.append({
                "question": f"How has {sales_column} trended over time?",
                "visualization_function": lambda df, date_col, sales_col: px.line(df.sort_values(by=date_col), x=date_col, y=sales_col, title=f"{sales_col} Over Time"),
                "columns": (date_column, sales_column)
            })
        if category_column:
            story_steps.append({
                "question": f"What is the distribution of {category_column}?",
                "visualization_function": lambda df, col: px.pie(df, names=col, title=f"Distribution of {col}"),
                "column": category_column
            })
        # Add more dynamic story steps based on available columns

        if not story_steps:
            st.info("No suitable columns selected for the data story.")
        else:
            current_step = st.session_state["story_step"]

            if current_step < len(story_steps):
                step_data = story_steps[current_step]
                st.subheader(f"Step {current_step + 1}: {step_data['question']}")

                try:
                    if "column" in step_data:
                        fig = step_data["visualization_function"](filtered_df, step_data["column"])
                        st.plotly_chart(fig)
                    elif "columns" in step_data:
                        fig = step_data["visualization_function"](filtered_df, *step_data["columns"])
                        st.plotly_chart(fig)
                except Exception as e:
                    st.error(f"Error generating visualization: {e}")

                if st.button("Next"):
                    st.session_state["story_step"] += 1
                    st.rerun()
            else:
                st.success("End of the data story!")
                if st.button("Restart Story"):
                    st.session_state["story_step"] = 0
                    st.rerun()

    # Tab 6: What-If Analysis
    with tab6:
        st.subheader("What-If Analysis")
        st.write("Experiment with hypothetical changes to your data.")

        if not numeric_columns:
            st.warning("No numerical columns available for What-If analysis.")
        else:
            selected_whatif_column = st.selectbox("Select a numerical column to modify", numeric_columns)
            percentage_change = st.number_input(f"Enter percentage change for {selected_whatif_column} (%)", step=1.0, value=0.0)

            if st.button("Apply What-If Change"):
                if selected_whatif_column:
                    try:
                        modified_whatif_df = filtered_df.copy()
                        change_factor = 1 + (percentage_change / 100)
                        modified_whatif_df[selected_whatif_column] = modified_whatif_df[selected_whatif_column] * change_factor

                        st.subheader("Original Data (Sample):")
                        st.dataframe(filtered_df.head())

                        st.subheader("Modified Data (Sample):")
                        st.dataframe(modified_whatif_df.head())

                        # Recalculate and display updated KPIs
                        st.subheader("Updated KPIs:")
                        kpi_cols = st.columns(len(kpi_data))
                        updated_kpi_data = {}
                        temp_con = duckdb.connect(database=':memory:', read_only=False)
                        temp_con.register('modified_data', modified_whatif_df)

                        if sales_column:
                            updated_kpi_data['total_sales'] = temp_con.execute(f'SELECT SUM("{sales_column}") FROM modified_data').fetchone()[0] or 0
                        updated_kpi_data['total_transactions'] = temp_con.execute("SELECT COUNT(*) FROM modified_data").fetchone()[0] or 0
                        if category_column:
                            updated_kpi_data['unique_categories'] = temp_con.execute(f'SELECT COUNT(DISTINCT "{category_column}") FROM modified_data').fetchone()[0] or 0
                        if date_column:
                            updated_kpi_data['date_range'] = temp_con.execute(f'SELECT MIN("{date_column}"), MAX("{date_column}") FROM modified_data').fetchone()

                        kpi_items = list(updated_kpi_data.items())
                        for i, (key, value) in enumerate(kpi_items):
                            with kpi_cols[i % len(kpi_cols)]:
                                if key == 'total_sales':
                                    st.metric(f"Total Sales (What-If)", f"${value:,.2f}")
                                elif key == 'total_transactions':
                                    st.metric(f"Total Transactions (What-If)", value)
                                elif key == 'unique_categories':
                                    st.metric(f"Unique Categories (What-If)", value)
                                elif key == 'date_range' and value and value[0] and value[1]:
                                    st.metric(f"Date Range (What-If)", f"{value[0].strftime('%Y-%m-%d')} - {value[1].strftime('%Y-%m-%d')}")
                                elif key == 'date_range':
                                    st.metric(f"Date Range (What-If)", "N/A")
                        temp_con.close()

                    except Exception as e:
                        st.error(f"An error occurred during What-If analysis: {e}")

    # Tab 7: Trivia Game
    with tab7:
        st.subheader("Data Trivia Game")
        st.write("Test your knowledge about the data!")

        if "trivia_score" not in st.session_state:
            st.session_state["trivia_score"] = 0
        if "current_question" not in st.session_state:
            st.session_state["current_question"] = None
        if "correct_answer" not in st.session_state:
            st.session_state["correct_answer"] = None
        if "options" not in st.session_state:
            st.session_state["options"] = []
        if "question_asked" not in st.session_state:
            st.session_state["question_asked"] = False

        def generate_trivia_question(df, num_cols, cat_cols):
            if not num_cols and not cat_cols:
                return None, None, None

            question_type = random.choice(["average", "value_counts"])

            if question_type == "average" and num_cols:
                col = random.choice(num_cols)
                correct_answer = df[col].mean()
                question = f"What is the average value of '{col}'?"
                options = [f"{correct_answer:.2f}", f"{df[col].median():.2f}", f"{df[col].min():.2f}", f"{df[col].max():.2f}"]
                random.shuffle(options)
                return question, f"{correct_answer:.2f}", options
            elif question_type == "value_counts" and cat_cols:
                col = random.choice(cat_cols)
                top_value = df[col].mode()[0] if not df[col].empty else "N/A"
                question = f"Which category appears most frequently in '{col}'?"
                value_counts = df[col].value_counts().nlargest(4).index.tolist()
                if top_value != "N/A" and top_value not in value_counts:
                    value_counts[-1] = top_value
                random.shuffle(value_counts)
                return question, top_value, value_counts

            return None, None, None

        if not st.session_state["question_asked"]:
            if numeric_columns or categorical_columns:
                st.session_state["current_question"], st.session_state["correct_answer"], st.session_state["options"] = generate_trivia_question(filtered_df, numeric_columns, categorical_columns)
                st.session_state["question_asked"] = True
            else:
                st.info("No suitable columns for trivia questions.")

        if st.session_state["current_question"]:
            st.subheader(st.session_state["current_question"])
            user_answer = st.radio("Select your answer:", st.session_state["options"])

            if st.button("Submit Trivia Answer"):
                if user_answer == str(st.session_state["correct_answer"]):
                    st.success("Correct!")
                    st.session_state["trivia_score"] += 1
                else:
                    st.error(f"Incorrect. The correct answer was: {st.session_state['correct_answer']}")
                st.session_state["question_asked"] = False
                st.session_state["current_question"] = None
                st.rerun()

            st.metric("Trivia Score", st.session_state["trivia_score"])
        elif not numeric_columns and not categorical_columns:
            if st.button("Play Trivia Again"):
                st.session_state["trivia_score"] = 0
                st.session_state["question_asked"] = False
                st.rerun()

    con.close()
else:
    st.info("ℹ️ Please upload a CSV file to begin.")