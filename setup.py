import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pymusical", # Replace with your own username
    version="0.1.1",
    author="Johannes Güting",
    author_email="jgueting@googlemail.com",
    description="A small converter for musical and physical values",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jgueting/pymusical",
    packages=setuptools.find_packages('pyparsing'),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)