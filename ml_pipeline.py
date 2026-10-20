"""
Run the ML pipeline
"""
import preprocessing.preprocessing_lou_original as preprocessing_lou_original


if __name__ == '__main__':
    housing = preprocessing_lou_original.load_gbcr_data()

    housing.info()

    housing["ocean_proximity"].value_counts()
    housing.describe()

    housing.hist(bins=50, figsize=(12, 8))
    plt.show()