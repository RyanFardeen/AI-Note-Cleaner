from setuptools import setup, find_packages

setup(
    name="ai-note-cleaner",
    version="1.0.0",
    description="AI-powered Apple Notes cleaner CLI (summarize, format, fix grammar using Perplexity AI)",
    author="Ryan Fardeen",
    license="MIT",
    packages=find_packages(),
    install_requires=[
        "rich",
        "markdown",
        "beautifulsoup4",
        "markdownify",
        "tabulate",
    ],
    entry_points={
        "console_scripts": [
            "ainotecleaner=ai_note_cleaner.cli:main",
        ],
    },
    python_requires=">=3.9",
)
