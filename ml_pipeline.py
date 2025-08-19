"""
Run the ML pipeline
"""
import preprocessing


if __name__ == '__main__':
    housing = preprocessing.load_gbcr_data()

    housing.info()

    housing["ocean_proximity"].value_counts()
    housing.describe()

    housing.hist(bins=50, figsize=(12, 8))
    plt.show()