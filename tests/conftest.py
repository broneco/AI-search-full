import os

# Force the test suite to use the dedicated 'ai_search_test' database.
# This environment override takes precedence over the .env file loading,
# securing the primary development database ('ai_search') from teardown wipes.
os.environ["POSTGRES_DB"] = "dolphin_ai_search_test"

