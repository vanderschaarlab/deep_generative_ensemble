import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve
import pandas as pd
import numpy as np
import os

from synthcity.plugins.core.dataloader import GenericDataLoader
from synthcity.utils import reproducibility

from DGE_utils import supervised_task, aggregate_imshow, aggregate, density_estimation, aggregate_predictive, cat_dl, compute_metrics, accuracy_confidence_curve

############################################################################################################
# Model training. Predictive performance


def predictive_experiment(X_gt, X_syns, task_type='mlp', results_folder=None, workspace_folder='workspace', load=True, save=True, plot=False):
    """Compares predictions by different approaches.

    Args:
        X_test (GenericDataLoader): Test data.
        X_syns (List(GenericDataLoader)): List of synthetic datasets.
        X_test (GenericDataLoader): Real data
        load (bool, optional): Load results, if available. Defaults to True.
        save (bool, optional): Save results when done. Defaults to True.

    Returns:

    """
    if save and results_folder is None:
        raise ValueError('results_folder must be specified when save=True.')

    X_test = X_gt.test()
    X_test.targettype = X_gt.targettype
    d = X_test.unpack(as_numpy=True)[0].shape[1]
    if not X_gt.targettype in ['regression', 'classification']:
        raise ValueError('X_gt.targettype must be regression or classification.')

    y_preds = {}

    # DGE (k=5, 10, 20)
    if len(X_syns) != 20:
        raise ValueError('X_syns assumed to have 20 elements in this experiment.')

    for k in [20, 10, 5]:
        
        y_pred_mean, y_pred_std, models = aggregate(
                X_test, X_syns[:k], supervised_task, models=None, workspace_folder=workspace_folder, task_type=task_type, load=load, save=save, filename=f'DGE_k{k}')
        
        if d == 2 and plot:
            aggregate_imshow(
                X_test, X_syns[:k], supervised_task, models=models, workspace_folder=workspace_folder, results_folder=results_folder, task_type=task_type, load=load, save=save, filename=f'DGE_k{k}')
        
        y_preds[f'DGE (k={k})'] = y_pred_mean

    
    # Single dataset single model
    y_naive = {'Naive (single)': [], 'Naive (ensemble)': []}
    for approach in y_naive.keys():
        for i in range(len(X_syns)):
            if approach == 'Naive (single)':
                X_syn_0 = [X_syns[i]]
            else:
                X_syn_0 = [X_syns[i]] * len(X_syns)
            
            y_pred_mean, y_pred_std, models = aggregate(
                    X_test, X_syn_0, supervised_task, models=None, workspace_folder=workspace_folder, task_type=task_type, load=load, save=save, filename=f'naive_m{i}_')
            
            if i==0 and d == 2 and 'ensemble' in approach:
                aggregate_imshow(
                    X_test, X_syn_0, supervised_task, models=models, results_folder=results_folder, task_type=task_type, load=load, save=save, filename=f'naive_m{i}_')
                
            if i==0 and 'ensemble' in approach:
                y_preds['Naive'] = y_pred_mean

            y_naive[approach].append(y_pred_mean)

    # Data aggregated
    # X_syn_cat = pd.concat([X_syns[i].dataframe()
    #                         for i in range(len(X_syns))], axis=0)
    # X_syn_cat = GenericDataLoader(X_syn_cat, target_column="target")
    # X_syn_cat.targettype = X_syns[0].targettype
    # X_syn_cat = [X_syn_cat]
    # #X_syn_cat = [X_syn_cat.sample(len(X_syns[0])) for _ in range(len(X_syns))]

    # y_pred_mean, y_pred_std, models = aggregate(
    #         X_test, X_syn_cat, supervised_task, models=None, workspace_folder=workspace_folder, task_type=task_type, load=load, save=save, filename='concat')

    # if d == 2 and plot:
    #     aggregate_imshow(
    #         X_test, X_syn_cat, supervised_task, models=models, results_folder=results_folder, workspace_folder=workspace_folder, task_type=task_type, load=load, save=save, filename='concat')
        
    # y_preds['Naive (concat)'] = y_pred_mean

    # Oracle
    X_oracle = X_gt.train()
    X_oracle.targettype = X_syns[0].targettype
    
    X_oracle = [X_oracle]
    
    if False:
        y_pred_mean, _, models = aggregate(
                X_test, X_oracle, supervised_task, models=None, workspace_folder=workspace_folder, task_type=task_type, load=load, save=save, filename='oracle')

        if d == 2 and plot:
            aggregate_imshow(
                X_test, X_oracle, supervised_task, models=models, results_folder=results_folder, workspace_folder=workspace_folder, task_type=task_type, load=load, save=save, filename='oracle')
        
        y_preds['Oracle (single)'] = y_pred_mean

    
    # Oracle ensemble
    X_oracle = X_oracle * len(X_syns)
    
    y_pred_mean, _, models = aggregate(
            X_test, X_oracle, supervised_task, models=None, workspace_folder=workspace_folder, task_type=task_type, load=load, save=save, filename='oracle')

    if d == 2 and plot:
        aggregate_imshow(
            X_test, X_oracle, supervised_task, models=models, results_folder=results_folder, workspace_folder=workspace_folder, task_type=task_type, load=load, save=save, filename='oracle')
        
    y_preds['Oracle'] = y_pred_mean




    if X_syns[0].targettype is 'classification':
        # Consider calibration of different approaches
        fig = plt.figure(figsize=(4, 4), tight_layout=False, dpi=200)
        for key, y_pred in y_preds.items():
            y_true = X_test.dataframe()['target'].values
            prob_true, prob_pred = calibration_curve(y_true, y_pred, n_bins=10)
            plt.plot(prob_pred, prob_true, label = key)
        
        plt.xlabel = 'Mean predicted probability'
        plt.ylabel = 'Fraction of positives'

        plt.plot([0, 1], [0, 1], linestyle='--', label='Perfect calibration')
        plt.legend()
        
        if save:
            filename = results_folder+'_calibration_curve.png'
            if not os.path.exists(results_folder):
                os.makedirs(results_folder)
            fig.savefig(filename, dpi=200)

        if plot:
            plt.show()
        
        plt.close()
        
        plt.figure(figsize=(4, 4), dpi=200, tight_layout=False)
        for key, y_pred in y_preds.items():
            y_true = X_test.dataframe()['target'].values
            thresholds, prob_true = accuracy_confidence_curve(y_true, y_pred, n_bins=20)
            plt.plot(thresholds, prob_true, label = key)
        
        plt.xlabel = r'Confidence threshold \tau'
        plt.ylabel = r'Accuracy on examples \hat{y}'

        plt.legend()
        
        if save:
            filename = results_folder+'_confidence_accuracy_curve.png'
            if not os.path.exists(results_folder):
                os.makedirs(results_folder)
            plt.savefig(filename, dpi=200)

        if plot:
            plt.show()
        
        plt.close()
    
    
    # Compute metrics
    del y_preds['Naive']

    scores = []
    for key, y_pred in y_preds.items():
        scores.append(compute_metrics(X_test.unpack(as_numpy=True)[1], y_pred, X_test.targettype))
    
    scores = pd.concat(scores, axis=0)
    scores.index = y_preds.keys()
    
    for approach in y_naive.keys():
        scores_naive = []
        for y_pred in y_naive[approach]:
            scores_naive.append(compute_metrics(X_test.unpack(as_numpy=True)[1], y_pred, X_test.targettype))
        
        
        scores_naive = pd.concat(scores_naive, axis=0)
        
        scores.loc[f'{approach} median'] = np.median(scores_naive,axis=0)
        scores.loc[f'{approach} mean'] = np.mean(scores_naive,axis=0)
        scores.loc[f'{approach} std'] = np.std(scores_naive, axis=0)
        scores.loc[f'{approach} min'] = np.min(scores_naive, axis=0)
        scores.loc[f'{approach} max'] = np.max(scores_naive, axis=0)

    return y_preds, scores

##############################################################################################################

# Model evaluation and selection experiments

def model_evaluation_experiment(X_gt, X_syns, model_type, relative=False, workspace_folder = 'workspace', load=True, save=True, verbose=False):
    means = []
    stds = []
    approaches = ['Oracle', 'Naive', 'DGE (K=5)', 'DGE (K=10)', 'DGE (K=20)']
    K = [None, None, 5, 10, 20]
    for i, approach in enumerate(approaches):
        if verbose:
            print('Approach: ', approach)
        folder = os.path.join(workspace_folder, approach)
        mean, std, _ = aggregate_predictive(
            X_gt, X_syns, models=None, task_type=model_type, workspace_folder=folder, load=load, save=save, approach=approach, relative=relative, verbose=verbose, K=K[i])
        means.append(mean)
        stds.append(std)

    means = pd.concat(means, axis=0)
    stds = pd.concat(stds, axis=0)
    means = means.round(3)
    stds = stds.round(3)
    
    means.index = approaches
    stds.index = approaches
    means.index.Name = 'Approach'
    stds.index.Name = 'Approach'
    return means, stds


def model_selection_experiment(X_gt, X_syns, relative='l1', workspace_folder='workspace', metric='accuracy', load=True, save=True):
    model_types = ['lr', 'mlp', 'deep_mlp', 'rf', 'knn', 'svm', 'xgboost']
    results = []
    means = []
    relative = 'l1'
    for i, model_type in enumerate(model_types):
        mean, std = model_evaluation_experiment(X_gt, X_syns, model_type, workspace_folder=workspace_folder, relative=relative, load=load, save=save)
        res = str(mean[metric]) + ' ± ' + str(std[metric])
        results.append(res)
        means.append(mean[metric])
    means = pd.concat(means, axis=1)
    approaches = ['oracle', 'naive', 'DGE']
    means.index = approaches
    means.columns = model_types
    results = pd.concat(results, axis=1)
    results.columns = model_types

    # sort based on oracle
    sorting = [model_types[i] for i in means.loc['oracle'].argsort()]
    means = means.loc[:, sorting]
    results = results.loc[:, sorting]
    
    print(results)
    means_sorted = means.loc[:, sorting]

    for approach in approaches:
        sorting_k = means_sorted.loc[approach].argsort()
        sorting_k = sorting_k.argsort()
        means_sorted.loc[approach+' rank'] = sorting_k.astype(int)+1

    means_sorted.iloc[3:].astype(int)
    print(means_sorted)
    
    return results, means_sorted


def model_predictive_uncertainty_experiment(X_gt, X_syns, model_type, workspace_folder=None, results_folder=None, load=True, save=True):

    if save and (results_folder is None or workspace_folder is None):
        raise ValueError('Please provide a workspace and results folder')
    if load and workspace_folder is None:
        raise ValueError('Please provide a workspace folder')
    
    


##############################################################################################################

# Predictive uncertainty with varying number of synthetic data points


def predictive_varying_nsyn(X_gt, X_syns, dataset, model_name, n_models, nsyn, results_folder, workspace_folder, load=True, save=True, verbose=True):
    # Generative uncertainty
    # Let us first look at the generative estimates
    nsyn = X_syns[0].shape[0]
    n_syns = [nsyn//100, nsyn//10, nsyn]
    if X_syns[0].targettype is not None and X_gt.shape[1] == 2:
        for n_syn in n_syns:
            ### DGE (k=20)
            X_syns_red = [GenericDataLoader(
                X_syns[i][:n_syn], target_column='target') for i in range(len(X_syns))]
            y_pred_mean, y_pred_std, models = aggregate_imshow(
                X_gt, X_syns_red, supervised_task, models=None, task_type='mlp', load=load, save=save, filename=f'n_syn{n_syn}_dge')

            ### DGE (k=10)
            X_syns_red = [GenericDataLoader(
                X_syns[i][:n_syn], target_column='target') for i in range(10)]
            y_pred_mean, y_pred_std, _ = aggregate_imshow(
                X_gt, X_syns_red, supervised_task, models=models[:10], task_type='mlp', load=load, save=save, filename=f'n_syn{n_syn}_dge_k=10')

            ### DGE (k=5)
            X_syns_red = [GenericDataLoader(
                X_syns[i][:n_syn], target_column='target') for i in range(5)]
            y_pred_mean, y_pred_std, _ = aggregate_imshow(
                X_gt, X_syns_red, supervised_task, models=models[:5], task_type='mlp', load=load, save=save, filename=f'n_syn{n_syn}_dge_k=5')

            # Single model
            # Now let's look at the same behaviour by a single data and a downstream DE
            index = 0
            X_syn_0 = [GenericDataLoader(X_syns[index][:n_syn], target_column='target')
                       for i in range(len(X_syns))]
            y_pred_mean, y_pred_std, _ = aggregate_imshow(
                X_gt, X_syn_0, supervised_task, models=[models[index] for i in range(len(X_syn_0))], task_type='mlp', load=False, save=save, filename=f'n_syn{n_syn}_naive')

            # Aggregated data
            # And what happens when using all data for the downstream DE?
            X_syn_cat = cat_dl(X_syns, n_limit=n_syn)
            X_syn_cat = [X_syn_cat for _ in range(len(X_syns))]
            #X_syn_cat = [X_syn_cat.sample(len(X_syns[0])) for _ in range(len(X_syns))]

            y_pred_mean, y_pred_std, models = aggregate_imshow(
                X_gt, X_syn_cat, supervised_task, models=None, task_type='mlp', load=load, save=save, filename=f'n_syn{n_syn}_concat')


#############################################################################################################

# Density estimation of synthetic data outputs

def density_experiment(X_gt, X_syns, load=True, save=True):
    # Density estimation experiment
    # Approximate density of synthetic data outputs

    X_test = X_gt.test()
    X_test.targettype = X_syns[0].targettype
    y_pred_mean, y_pred_std, models = aggregate_imshow(
        X_test, X_syns, density_estimation, models=None, task_type='kde', load=load, save=save)
