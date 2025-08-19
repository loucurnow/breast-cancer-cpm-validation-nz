from pathlib import Path
import numpy as np
import pandas as pd
import tarfile
import urllib.request
import pyreadr
import matplotlib.pyplot as plt
from tabulate import tabulate

from preprocessing import load_gbcscs


# function to create a table where key characteristics are summarised
# should work for both bcf and german datasets
def summarise_vars():
    """

    vars:
        total number of participants
        median followup (years)
        number of breast cancer deaths
        number of other deaths
        annual breast cancer mortality rate
        five year breast cancer survival rate
        median age at diagnosis, years +- SD
        median year of diagnosis, +- SD

        groups
        gender (NA since all female)

        menopausal status
        pre
        post

        referral source
        screened
        symptomatic

        tumour size
        <10
        10-19
        20-29
        30-49
        50+

        grade
        I
        II
        III

        nodes
        T1
        T2
        T3
        T4

        estrogen receptor status
        ER negative
        ER positive

        progesterone receptor status
        PR negative
        PR positive

        her2 status
        positive
        negative

        ki67 proliferation index >20%
        positive
        negative
        not done


        adjuvant therapy
        chemotherapy
            - groups for generations?

        hormone therapy
        biological targeted therapy
            - traz, bis?
        radiotherapy
            - number of grays?
        combination


        smoking status
        current or historical
        never smoked



    :return:
    """

if __name__ == '__main__':
    df = load_gbcscs()
    print(df)
