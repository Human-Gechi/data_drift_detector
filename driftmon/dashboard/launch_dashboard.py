import os


def _main():
    try:
        dashboard_path = os.path.join(os.path.dirname(__file__), "main.py")
        os.system(f'streamlit run "{dashboard_path}"')
    except KeyboardInterrupt:
        pass
