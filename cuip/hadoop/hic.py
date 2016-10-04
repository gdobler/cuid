__author__ = "Mohit Sharma"

from pyspark import SparkConf, SparkContext
from pyspark.sql import SQLContext
from pyspark.sql.types import StructType, StructField, StringType, DoubleType
import numpy as np
import os

APP_NAME = "Hadoop_Image_Cluster"

class HadoopImageCluster(object):
    """
    Hadoop Image Cluster
    """
    def __init__(self, sc, path=None, fname=None, fname_ext=None):
        """
        Parameters
        ----------
        sc: `SparkContext`, optional
        path: str
            Location in hdfs containing files
        example: `/user/<username>/<dir>`
        fname: str, optional
            filename to be processed
        fname_ext: str
            extension for binary filenames
        """
        conf = SparkConf().setAppName(APP_NAME)
        conf = conf.set("spark.executor.memory", "2g")
        conf = conf.set("spark.executor.cores", "10")
        if sc:
            self.sc = sc
        else:
            self.sc = SparkContext(conf=conf)
        self.sqlcontext = SQLContext(self.sc)
        self.path = path
        self.fname = fname
        self.fname_ext = fname_ext

        self.img_rdd = self._getImgRDD(self.path, 
                                       self.fname, 
                                       self.fname_ext)


    def _getImgRDD(self, path, fname, fname_ext):
        """
        Return rdd of binary files converted to 
        numpy arrays
        Parameters
        ----------
        path: str
            Location in hdfs containing files
            example: `/user/<username>/<dir>`                                                                                                                               
        fname: str, optional
            filename to be processed
        fname_ext: str
            extension for binary filenames
        """
        if fname:
            imgpair = self.sc.binaryFiles(os.path.join(path, fname))
        else:
            # /<path>/*.raw
            imgpair = self.sc.binaryFiles(os.path.join(path, "*."+fname_ext))
        
        rdd = imgpair.map(lambda (x,y): (x, (np.asarray(bytearray(y), 
                                                        dtype=np.uint8))))
        return rdd

    def mean(self, n, nrows, ncols, ndims, asdf=True):
        """
        Return the mean of the n-dim numpy array
        img_arr: numpy array
            n-dimensional array
        n: int
            if arrays are vertically stacked, n is the 
            total number of stacked arrays
        nrows: int
            number of rows (per stacked array)
        ncols: int
            number of columns (per stacked array)
        ndims: int
            `n` dimensions
        asdf: bool
            True: return the output as a dataframe
                To see the output, df.show(truncate=False)
            False: return the output as RDD
                To see the output, rdd.collect()

        """
        def _mean(x):
            def _perDim(img, ndims):
                """
                Returns mean of every dimension for an array
                """
                mean_per_dim = []
                for d in range(ndims):
                    mean_per_dim.append(np.mean(img[:,:,d]))
                return mean_per_dim

            # Return mean for all stacked images and their dimensions
            return [_perDim(
                    x[i*nrows*ncols*ndims : (i+1)*nrows*ncols*ndims].reshape(nrows, ncols, ndims), 
                    ndims) 
                    for i in range(n)]
        mean_rdd = self.img_rdd.mapValues(_mean)
        if not asdf:
            return mean_rdd
        else:
            mean_formatted = mean_rdd.map(lambda x: (os.path.basename(x[0]), 
                                                     float(x[1][0][1]), 
                                                     float(x[1][1][1]), 
                                                     float(x[1][2][1])
                                                     ))
            # Dataframe Structure
            schema = StructType([StructField("Filename", StringType(), True), 
                                 StructField("CH0", DoubleType(), True), 
                                 StructField("CH1", DoubleType(), True), 
                                 StructField("CH2", DoubleType(), True)
                                 ])
            
            df = self.sqlcontext.createDataFrame(mean_formatted, schema)
            return df
            
"""
def mean(sc, rdd, stacked, n, nrows, ncols, ndims):
    
    Obtain mean of the image
    Parameters
    ----------
    sc: `SparkContext`
    rdd: `pyspark.rdd` 
        dataset containing binary raw file
        example: rdd = sc.binaryFiles('/path/to/raw/file')
    stacked: bool
        If the rdd contains stacked images (to improve namenode efficiency)
    n: int
        if stacked == `True`, n is the number of stacked images
    nrows: int
        number of rows per image (per stacked image)
    ncols: int
        number of columns per image (per stacked image)
    ndims: int
        number of dimensions per image (eg. 3 for RGB image)
    
    # Collect the data to create a numpy array.
    # -- Research a better way -- #
    img_rdd = rdd.collect()
    img_series = np.asarray(bytearray(img_rdd[0][1]), dtype=np.uint8)
    data = []

    def _mean(x): 
        mean1 = np.mean(x[:,:,0])
        mean2 = np.mean(x[:,:,1])
        mean3 = np.mean(x[:,:,2])
        return ('ch0',mean1), ('ch1', mean2), ('ch3', mean3)

    # For n stacked images, extract individual image and tag them
    for i in range(n):
        data.append(
            ('img'+str(i), 
             img_series[i*nrows*ncols*ndims : (i+1)*nrows*ncols*ndims].reshape(nrows, ncols, ndims)
             ))
    
    # Distribute the data to all the nodes
    rdd = sc.parallelize(data)
    # Map mean function on every image
    return rdd.mapValues(_mean)
   
""" 

if __name__ == "__main__":
    # Obtain Mean        
    f_path = '/user/mohitsharma44/uo_images'
    f_ext = 'raw'
    rows = 2160
    cols = 4096
    dims = 3
    combined = 4
    hic = HadoopImageCluster(sc=None, path=f_path, fname=None, fname_ext=f_ext)
    df = hic.mean(combined, nrows=rows, ncols=cols, ndims=dims, asdf=True)
    df.show(truncate = False)