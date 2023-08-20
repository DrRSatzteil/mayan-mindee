from setuptools import setup

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="mayanmindee",
    version="0.1",
    description="Enhance your Mayan EDMS documents with metadata read from Mindee API",
    license="tbd",
    long_description=long_description,
    author="Thomas Lauterbach",
    author_email="drrsatzteil@web.de",
    url="http://www.tbd.de/",
    packages=["mayanmindee"],
    python_requires=">=3.8.0",
    install_requires=[
        "wheel",
        "requests",
        "redis",
        "rq",
        "Flask",
        "mindee",
        "gunicorn",
        "schwifty",
        "thefuzz",
        "python-Levenshtein",
        "PyPDF2"
    ],
)
