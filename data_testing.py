from __future__ import print_function, division
import os
import torch
import pandas as pd
from skimage import io, transform
import numpy as np
import matplotlib.pyplot as plt
import SimpleITK as sitk
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, utils
import csv
import scipy

# Ignore warnings
import warnings
warnings.filterwarnings("ignore")

def load_itk_image(filename):
    itkimage = sitk.ReadImage(filename)
    numpyImage = sitk.GetArrayFromImage(itkimage)

    numpyOrigin = np.array(list(reversed(itkimage.GetOrigin())))
    numpySpacing = np.array(list(reversed(itkimage.GetSpacing())))

    return numpyImage, numpyOrigin, numpySpacing


def readCSV(filename):
    lines = []
    with open(filename, "r") as f:
        csvreader = csv.reader(f)
        for line in csvreader:
            lines.append(line)
    return lines


def worldToVoxelCoord(worldCoord, origin, spacing):
    stretchedVoxelCoord = np.absolute(worldCoord - origin)
    voxelCoord = stretchedVoxelCoord / spacing
    return voxelCoord

def voxelToWorldCoord(voxelCoord, origin, spacing):
    stretchedVoxelCoord = voxelCoord * spacing
    worldCoord = stretchedVoxelCoord + origin
    return worldCoord


def normalizePlanes(npzarray):
    maxHU = 400.
    minHU = -1000.

    # npzarray = (npzarray - minHU) / (maxHU - minHU)
    npzarray = (npzarray + 600) / (300)
    npzarray[npzarray > 1] = 1.
    npzarray[npzarray < 0] = 0.
    return npzarray

def show_center(image, center):
    plt.imshow(image)
    plt.scatter([center[1]],[center[2]], s=10, marker='.', c='r')
    plt.pause(0.001)

def file_exists(record, root_dir, subset):
    for idx in subset:
        path = os.path.join(root_dir,'subset'+str(idx), str(record[0])+'.mhd')
        if os.path.exists(path):
            return True
    return False

def get_subset(record, root_dir, subset):
    for idx in subset:
        path = os.path.join(root_dir,'subset'+str(idx), str(record[0])+'.mhd')
        if os.path.exists(path):
            return idx
    return -1

class Luna16DatasetTest(Dataset):
    def __init__(self, csv_file, root_dir, subset, transform = None):
        self.center_frame = readCSV(csv_file)
        self.center_frame = self.center_frame[1:]
        self.root_dir = root_dir
        self.subset = subset
        self.center_frame = [record+[str(get_subset(record, self.root_dir, subset))]
                             for record in self.center_frame if file_exists(record, self.root_dir, subset)]
        print(len(self.center_frame))
        print('center_frame\' s length is: '+str(len(self.center_frame)))
        self.transform = transform

    def __len__(self):
        return len(self.center_frame)

    def __getitem__(self, idx):
        cube_name = os.path.join(self.root_dir, 'subset'+self.center_frame[idx][5],
                                 self.center_frame[idx][0]+'.mhd')
        numpyImage, numpyOrigin, numpySpacing = load_itk_image(cube_name)

        # # calculate resize factor
        # RESIZE_SPACING = [1, 1, 1]
        # resize_factor = numpySpacing / RESIZE_SPACING
        # new_real_shape = numpyImage.shape * resize_factor
        # new_shape = np.round(new_real_shape)
        # real_resize = new_shape / numpyImage.shape
        # new_spacing = numpySpacing / real_resize
        #
        # # resize image
        # lung_img = scipy.ndimage.interpolation.zoom(numpyImage, real_resize)
        #
        # lung_img_512 = np.zeros((lung_img.shape[0], 512, 512))
        # original_shape = lung_img.shape
        # for z in range(lung_img.shape[0]):
        #     offset = (512 - original_shape[1])
        #     upper_offset = int(np.round(offset / 2))
        #     lower_offset = offset - upper_offset
        #
        #     new_origin = ([-upper_offset, -lower_offset, 0], numpyOrigin, new_spacing)
        #
        #     lung_img_512[z, upper_offset:-lower_offset, upper_offset:-lower_offset] = lung_img[z, :, :]


        cand = self.center_frame[idx]
        worldCoord = np.asarray([float(cand[3]), float(cand[2]), float(cand[1])])
        voxelCoord = worldToVoxelCoord(worldCoord, numpyOrigin, numpySpacing)
        voxelWidth = 40
        voxelDepth = 24
        coord_start = [0, 0, 0]
        coord_end = [0, 0, 0]
        coord_start[0] = int(voxelCoord[0] - voxelDepth / 2.0)
        coord_end[0] = int(voxelCoord[0] + voxelDepth / 2.0)
        coord_start[1] = int(voxelCoord[1] - voxelWidth / 2.0)
        coord_end[1] = int(voxelCoord[1] + voxelWidth / 2.0)
        coord_start[2] = int(voxelCoord[2] - voxelWidth / 2.0)
        coord_end[2] = int(voxelCoord[2] + voxelWidth / 2.0)
        patch = numpyImage[coord_start[0]:coord_end[0], coord_start[1]:coord_end[1], coord_start[2]:coord_end[2]]
        patch = normalizePlanes(patch)
        label = int(cand[4])
        sample = {'cube':patch, 'label': label}

        if self.transform:
            sample = self.transform(sample)

        return sample

class ToTensor(object):
    def __call__(self, sample):
        cube, label = sample['cube'], sample['label']
        cube = np.expand_dims(cube,0)
        return {'cube':torch.from_numpy(cube.copy()).float(), 'label': label}

# flip = RandomFlip((20,36,36))
# crop = RandomCrop((20,36,36))
if __name__ == '__main__':
    plt.ion()  # interactive mode
    root_path = '/Users/hyacinth/Downloads/TUTORIAL/data/'
    cand_path = '/Users/hyacinth/Downloads/TUTORIAL/data/candidates.csv'

    transformed_dataset = Luna16DatasetTest(csv_file=cand_path, root_dir=root_path, subset=[0],
                                        transform=transforms.Compose(
                                            [ToTensor()]))
    dataloader = DataLoader(transformed_dataset, batch_size=1, shuffle=True, num_workers=4)

    for i_batch, sample_batched in enumerate(dataloader):
        print(i_batch, sample_batched['cube'].size(), sample_batched['label'].size())
        fig = plt.figure()
        img = sample_batched['cube']
        img = img[0][0][10].numpy()
        plt.imshow(img, cmap='gray')
        plt.show()

    print('ends')
