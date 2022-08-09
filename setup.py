from setuptools import find_packages, setup

requirements = []

setup(
    packages=find_packages(exclude=["docs"]),
    python_requires=">=3.7",
    install_requires=requirements,
    include_package_data=True,
)
