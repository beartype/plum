from setuptools import find_packages, setup, Extension


setup(
    packages=find_packages(exclude=["docs"]),
    python_requires=">=3.6",
    install_requires=[],
    include_package_data=True,
)
