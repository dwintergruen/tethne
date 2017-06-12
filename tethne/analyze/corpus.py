"""
Methods for analyzing :class:`.Corpus` objects.

.. autosummary::
   :nosignatures:

   burstness
   feature_burstness
   sigma

"""

import networkx as nx
import warnings

from mpmath import mp
from math import exp, log
from collections import defaultdict
from multiprocessing import Pool

from tethne.utilities import argmin, mean
import sys
from sympy.physics.vector.printing import params
import logging
logger = logging.getLogger("main")

PYTHON_3 = sys.version_info[0] == 3
if PYTHON_3 == 3:
    str = str
    xrange = range


def _forward(X, s=mp.mpf(1.1), gamma=mp.mpf(1.), k=5):
    cnt=[0,0]
    """
    Forward dynamic algorithm for burstness automaton HMM, from `Kleinberg
    (2002) <http://www.cs.cornell.edu/home/kleinber/bhs.pdf>`_.

    Parameters
    ----------
    X : list
        A series of time-gaps between events.
    s : float
        (default: 1.1) Scaling parameter ( > 1.)that controls graininess of
        burst detection. Lower values make the model more sensitive.
    gamma : float
        (default: 1.0) Parameter that controls the 'cost' of higher burst
        states. Higher values make it more 'difficult' to achieve a higher
        burst state.
    k : int
        (default: 5) Number of states. Higher values increase computational
        cost of the algorithm. A maximum of 25 is suggested by the literature.

    Returns
    -------
    states : list
        Optimal state sequence.
    """
    X = list(X)
    T = sum(X)
    n = len(X)
    
    def alpha(i):
        return mp.mpf(n/T)*mp.mpf(s**i)

    def tau(i, j):
        if j > i:
            return mp.mpf(j-i)*gamma*mp.ln(mp.mpf(n))
        return mp.mpf(0.)

    def f(j, x):
        #print("(J,X):",j,x,n,alpha(j))
        #print("ALPHA:",alpha(j) * exp(-1. * alpha(j) * x))
        return mp.mpf(alpha(j)) * mp.exp(mp.mpf(-1.) * alpha(j) * x)

    def C(j, t):
        
        if j == 0 and t == 0:
            return mp.mpf(0.)
        elif t == 0:
            return mp.mpf("inf")

        C_tau = min([C_values[l][t-1] + tau(l, j) for l in range(k)])
        #try:
        return (mp.mpf(-1.) * mp.ln(mp.mpf(f(j,X[t])))) + C_tau
        #except:
        #    cnt[1]+=1
        #    return Decimal(-1.) * Decimal("inf") #can happen if f-> 0

   

    # C() requires default (0) values, so we construct the "array" in advance.
    C_values = [[0 for t in range(len(X))] for j in range(k)]
    for j in range(k):
        for t in range(len(X)):
            try:
                C_values[j][t] = C(j,t)
            except:
                logger.error("states cannot be calculates: j %s t %s"%(j,t))
                logger.error("states cannot be calculates: %s"%repr(C_values))
                C_values[j][t] = mp.mpf("inf")
                
    # Find the optimal state sequence.
    #set_trace()
    try:
        states = [argmin([c[t] for c in C_values]) for t in range(n)]
    except:
        logger.error("states cannot be calculates: %s"%repr(C_values))
        states = None
        
    return states

def _top_features(corpus, feature, topn=20, perslice=False, axis='date'):
    warnings.warn("Removed in 0.8. Use corpus.top_features() instead.",
                  DeprecationWarning)
    return corpus.top_features(feature, topn=topn, perslice=perslice)

def burstness(corpus, featureset_name, features=[], k=5, topn=20, workers=5,
              perslice=False, normalize=True, **kwargs):
    """
    Estimate burstness profile for the ``topn`` features (or ``flist``) in
    ``feature``.

    Uses the popular burstness automaton model inroduced by `Kleinberg (2002)
    <http://www.cs.cornell.edu/home/kleinber/bhs.pdf>`_.

    Parameters
    ----------
    corpus : :class:`.Corpus`
    feature : str
        Name of featureset in ``corpus``. E.g. ``'citations'``.
    k : int
        (default: 5) Number of burst states.
    topn : int or float {0.-1.}
        (default: 20) Number (int) or percentage (float) of top-occurring
        features to return. If ``flist`` is provided, this parameter is ignored.
    perslice : bool
        (default: False) If True, loads ``topn`` features per slice. Otherwise,
        loads ``topn`` features overall. If ``flist`` is provided, this
        parameter is ignored.
    flist : list
        List of features. If provided, ``topn`` and ``perslice`` are ignored.
    normalize : bool
        (default: True) If True, burstness is expressed relative to the hightest
        possible state (``k-1``). Otherwise, states themselves are returned.
    kwargs : kwargs
        Parameters for burstness automaton HMM.

    Returns
    -------
    B : dict
        Keys are features, values are tuples of ( dates, burstness )

    Examples
    --------

    .. code-block:: python

       >>> from tethne.analyze.corpus import burstness
       >>> B = burstness(corpus, 'abstractTerms', flist=['process', 'method']
       >>> B['process']
       ([1990, 1991, 1992, 1993], [0., 0.4, 0.6, 0.])

    """

    # If `features` of interest are not specified, calculate burstness for the
    #  top `topn` features.
    if len(features) == 0:
        T = corpus.top_features(featureset_name, topn=topn, perslice=perslice)
        if perslice:
            features = list(set([f[0] for flist in zip(*T)[1] for f in flist]))
        else:
            features = list(zip(*T))[0]


    if workers == 1:
        logger.info("single process")
        B = {feature: feature_burstness(corpus, featureset_name, feature, k=k,
                                        normalize=normalize, **kwargs) for feature in features}
             
    else:
        logger.info("%s processes"%workers)

        params=[]
        len_per_worker = int(len(features)/workers)
    
        if 'date' not in corpus.indices:
            corpus.index('date')
    
        if featureset_name not in corpus.features:
            corpus.index_feature(featureset_name)
        
        # Get time-intervals between occurrences.
       
        
        dates = [min(corpus.indices['date'].keys()) - 1]    # Pad start.
    
        for i in range(workers+1):        
            #p = (corpus, featureset_name, features[i*len_per_worker:(i+1)*len_per_worker], k, normalize, 1.1, 1.)  
            
            
            feature_distributions = [ corpus.feature_distribution(featureset_name,f) for f in features[i*len_per_worker:(i+1)*len_per_worker]]
              
            p = (i,dates,feature_distributions, featureset_name, features[i*len_per_worker:(i+1)*len_per_worker], k, normalize, 1.1, 1.) 
            
            params.append(p)
        
        logger.info("starting_pool")
        p = Pool(workers)
       
        Bs = p.map(feature_burstness_wrapper,params)
        
        B={}
        for tmp_B in Bs:
            B.update(tmp_B)
            
      
    return B


def feature_burstness_wrapper(param):
    
    nr, dates, feature_distributions, featureset_name, features, k, normalize, s, gamma = param

    B = {}
    max_n = len(features)
    n=0
    #print("%s : %s of %s"%(nr,n,max_n))
            
    for feature,feature_distribution in  zip(features,feature_distributions):
        if max_n > 10:
            if n/3 == int(n/3):
                logger.info("%s : %s of %s"%(nr,n,max_n))
        else:
            logger.info("%s : %s of %s"%(nr,n,max_n))
        n+=1
            
        B[feature] = feature_burstness(None,featureset_name, feature, feature_distribution=feature_distribution, dates=dates, k=k,normalize=normalize,s =s,gamma=gamma)


    # B = {feature: feature_burstness(None,featureset_name, feature, feature_distribution=feature_distribution, dates=dates, k=k,normalize=normalize,s =s,gamma=gamma) 
    #     for feature,feature_distribution in  zip(features,feature_distributions)}
        
    return  B
     
def feature_burstness(corpus, featureset_name, feature, k=5, normalize=True,
                      s=1.1, gamma=1., dates=None ,feature_distribution=None, **slice_kwargs):
    """
    Estimate burstness profile for a feature over the ``'date'`` axis.

    Parameters
    ----------
    corpus : :class:`.Corpus`
    feature : str
        Name of featureset in ``corpus``. E.g. ``'citations'``.
    findex : int
        Index of ``feature`` in ``corpus``.
    k : int
        (default: 5) Number of burst states.
    normalize : bool
        (default: True) If True, burstness is expressed relative to the hightest
        possible state (``k-1``). Otherwise, states themselves are returned.
    kwargs : kwargs
        Parameters for burstness automaton HMM.
    """


    if corpus is not None:
        if featureset_name not in corpus.features:
            corpus.index_feature(featureset_name)
        
    if dates is None:
        if 'date' not in corpus.indices:
            corpus.index('date')
    
        # Get time-intervals between occurrences.
       
        
        dates = [min(corpus.indices['date'].keys()) - 1]    # Pad start.
    
    X_ = [mp.mpf(1.)]

    
    if feature_distribution is None:
        years, values = corpus.feature_distribution(featureset_name, feature)
    else:
        years, values = feature_distribution
        
    for year, N in zip(years, values):
        if N == 0:
            continue

        if N > 1:
            if year == dates[-1] + 1:
                for n in range(int(N)):
                    X_.append(mp.mpf(1.)/mp.mpf(N))
                    dates.append(year)
            else:
                X_.append(mp.mpf(year - dates[-1]))
                dates.append(year)
                for n in range(int(N) - 1):
                    X_.append(mp.mpf(1.)/mp.mpf(N - 1))
                    dates.append(year)
        else:
            X_.append(mp.mpf(year - dates[-1]))
            dates.append(year)
            
    # Get optimum state sequence.
    st = _forward([x*100 for x in X_], s=s, gamma=gamma, k=k)

    if st is None:
        logger.error("NO state for: %s %s"%(feature,featureset_name))
        return None

    # Bin by date.
    A = defaultdict(list)
    for i in range(len(X_)):
        A[dates[i]].append(st[i])

    # Normalize.
    if normalize:
        A = {key: mean(values)/k for key, values in list(A.items())}
    else:
        A = {key: mean(values) for key, values in list(A.items())}

    D = sorted(A.keys())
    return D[1:], [A[d] for d in D[1:]]


def sigma(G, corpus, featureset_name, B=None, **kwargs):
    """
    Calculate sigma (from `Chen 2009 <http://arxiv.org/pdf/0904.1439.pdf>`_)
    for all of the nodes in a :class:`.GraphCollection`\.

    You can set parameters for burstness estimation using ``kwargs``:

    =========   ===============================================================
    Parameter   Description
    =========   ===============================================================
    s           Scaling parameter ( > 1.)that controls graininess of burst
                detection. Lower values make the model more sensitive. Defaults
                to 1.1.
    gamma       Parameter that controls the 'cost' of higher burst states.
                Defaults to 1.0.
    k           Number of burst states. Defaults to 5.
    =========   ===============================================================

    Parameters
    ----------
    G : :class:`.GraphCollection`
    corpus : :class:`.Corpus`
    feature : str
        Name of a featureset in `corpus`.


    Examples
    --------

    Assuming that you have a :class:`.Corpus` generated from WoS data that has
    been sliced by ``date``.

    .. code-block:: python

       >>> # Generate a co-citation graph collection.
       >>> from tethne import GraphCollection
       >>> kwargs = { 'threshold':2, 'topn':100 }
       >>> G = GraphCollection()
       >>> G.build(corpus, 'date', 'papers', 'cocitation', method_kwargs=kwargs)

       >>> # Calculate sigma. This may take several minutes, depending on the
       >>> #  size of your co-citaiton graph collection.
       >>> from tethne.analyze.corpus import sigma
       >>> G = sigma(G, corpus, 'citations')

       >>> # Visualize...
       >>> from tethne.writers import collection
       >>> collection.to_dxgmml(G, '~/cocitation.xgmml')

    In the visualization below, node and label sizes are mapped to ``sigma``,
    and border width is mapped to ``citations``.

    .. figure:: _static/images/cocitation_sigma2.png
       :width: 600
       :align: center

    """
    if 'date' not in corpus.indices:
        corpus.index('date')

    # Calculate burstness if not provided.
    if not B:
        B = burstness(corpus, featureset_name, features=G.nodes(), **kwargs)

    Sigma = {}      # Keys are dates (from GraphCollection), values are
                    #  node:sigma dicts.
    for key, graph in list(G.items()):
        centrality = nx.betweenness_centrality(graph)
        sigma = {}  # Sigma values for all features in this year.
        attrs = {}  # Sigma values for only those features in this graph.
        for n_, burst in list(B.items()):
            burst = dict(list(zip(*burst)))     # Reorganize for easier lookup.

            # Nodes are indexed as integers in the GraphCollection.
            n = G.node_lookup[n_]

            # We have burstness values for years in which the feature ``n``
            #  occurs, and we have centrality values for years in which ``n``
            #  made it into the graph.
            if n in graph.nodes() and key in burst:
                sigma[n] = ((centrality[n] + 1.) ** burst[key]) - 1.
                attrs[n] = sigma[n]

        # Update graph with sigma values.
        nx.set_node_attributes(graph, 'sigma', attrs)
        Sigma[key] = sigma

    # Invert results and update the GraphCollection.master_graph.
    # TODO: is there a more efficient way to do this?
    inverse = defaultdict(dict)
    for gname, result in list(Sigma.items()):
        if hasattr(result, '__iter__'):
            for n, val in list(result.items()):
                inverse[n].update({gname: val})
    nx.set_node_attributes(G.master_graph, 'sigma', inverse)

    # We want to return results in the same format as burstness(); with node
    #  labels as keys; values are tuples ([years...], [sigma...]).
    return {n: list(zip(*list(G.node_history(G.node_lookup[n], 'sigma').items())))
            for n in list(B.keys())}
