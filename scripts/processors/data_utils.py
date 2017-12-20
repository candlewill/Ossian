from sklearn import preprocessing
import numpy as np


def load_binary_file_frame(file_name, dimension):
    """
    Load binary file.

    Args:
        file_name: Binary file names.
        dimension: The specified dimension.

    Returns: A tuple (features, frame_number), where features is a numpy array of shape [-1, dimension],
             and frame_number is the frame number.

    """
    fid_lab = open(file_name, 'rb')
    features = np.fromfile(fid_lab, dtype=np.float32)
    fid_lab.close()
    assert features.size % float(dimension) == 0.0, 'specified dimension %s not compatible with data' % (dimension)
    frame_number = features.size // dimension
    features = features[:(dimension * frame_number)]
    features = features.reshape((-1, dimension))

    return features, frame_number


def load_norm_stats(stats_file, dim, method="MVN"):
    #### load norm stats ####
    norm_matrix, frame_number = load_binary_file_frame(stats_file, dim)
    assert frame_number == 2

    if method == "MVN":
        scaler = preprocessing.StandardScaler()
        scaler.mean_ = norm_matrix[0, :]
        scaler.scale_ = norm_matrix[1, :]
    elif method == "MINMAX":
        scaler = preprocessing.MinMaxScaler(feature_range=(0.01, 0.99))
        scaler.min_ = norm_matrix[0, :]
        scaler.scale_ = norm_matrix[1, :]

    return scaler


def norm_data(data, scaler, sequential_training=False):
    if scaler is None:
        return

    #### normalize data ####
    if not sequential_training:
        data = scaler.transform(data)
    else:
        for filename, features in data.iteritems():
            data[filename] = scaler.transform(features)

    return data


def denorm_data(data, scaler):
    if scaler is None:
        return

    #### de-normalize data ####
    data = scaler.inverse_transform(data)

    return data
