import torch
import json
from tqdm import tqdm
import pandas as pd
import os
from time import time

from autonomous_driving.dataset import Drive360Loader
from autonomous_driving.utils import add_results, get_device
from autonomous_driving.config import *
from autonomous_driving.basic import SomeDrivingModel

if __name__ == "__main__":
    config = json.load(open(CONFIG_FILE))
    device = get_device()
    test_loader = Drive360Loader(config, "test")
    model = torch.load(TRAINED_MODELS_DIR + "1571333078.746423_angle.pt")
    model = model.to(device)

    # Creating a submission file.
    normalize_targets = config['target']['normalize']
    target_mean = config['target']['mean']
    target_std = config['target']['std']

    results = {
        "chapter": [],
        "frameIndex": [],
        "canSteering": [],
        "canSpeed": [],
    }

    with torch.no_grad():
        for batch_idx, (data, target, ids) in enumerate(tqdm(test_loader)):
            # transfer stuff to GPU
            data, target = test_loader.load_batch_to_device(data, target, device)

            prediction = model(data)
            add_results(results, prediction, ids, normalize_targets, target_mean, target_std)
            # Used to terminate early, remove.
            # if batch_idx >= 5:
            #     break

    print("results: ", len(results))
    print("test_file: ", len(test_loader.drive360))
    # Assuming sampled_predictions_file only has columns ["chapter", "frameIndex", "canSteering", "canSpeed"]
    # Also frame index is integer
    sampled_predictions = pd.DataFrame.from_dict(results)
    sampled_predictions.loc[:, "chapter"] = sampled_predictions.apply(lambda s: int(s.loc["chapter"]), axis=1)
    sampled_predictions.loc[:, "frameIndex"] = sampled_predictions.apply(lambda s: int(s.loc["frameIndex"]), axis=1)
    # sampled_predictions.chapter = pd.to_numeric(sampled_predictions.chapter)
    # sampled_predictions.frameIndex = pd.to_numeric(sampled_predictions.frameIndex)

    # sampled_predictions.to_csv(SUBMISSIONS_DIR + "test_sample1.csv")

    test_full = pd.read_csv(DATA_DIR + "test_full.csv", usecols=["chapter", "cameraFront"])

    # # Create an frame number column in both sampled_predictions and test_full
    print("creating frameIndex on test_full")
    since = time()
    test_full["frameIndex"] = test_full.apply(lambda row: int(os.path.basename(row.cameraFront).split(".")[0][3:]),
                                              axis=1)
    test_full = test_full[["chapter", "frameIndex"]]
    print("done in ", time() - since, "\n")

    # Join test_full with sampled_predictions => left join
    print("merging test_full and sampled_predictions")
    since = time()
    tm = pd.merge(test_full, sampled_predictions, how="left", left_on=["chapter", "frameIndex"],
                  right_on=["chapter", "frameIndex"])
    print("merged in ", time() - since, "\n")

    del sampled_predictions
    del test_full

    print("interpolating values")
    since = time()
    tm = tm.groupby('chapter').apply(
        lambda s: s.interpolate(method='from_derivatives').interpolate('linear', limit_direction="both")
    )
    print("interpolated in ", time() - since, "\n")

    print("filtering >100 rows")
    since = time()
    tm = tm.loc[tm.frameIndex > 100]
    print("filtered in ", time() - since, "\n")

    tm.canSpeed = tm.canSpeed.clip(lower=0)
    tm[["canSteering", "canSpeed"]].to_csv(SUBMISSIONS_DIR + "submission_full_interpolate.csv")
