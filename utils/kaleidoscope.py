from torchvision.transforms import ToTensor
from torchvision.transforms import ToPILImage
from torchvision.datasets import MNIST
import torch
import numpy
import PIL

class Kaleidoscope:
    """
    A class of methods that spatially rearrange the activation vector to mimic
    the effect of a kaleidoscope, and also rearrange the weight matrix
    correspondingly. 
    """

    def __init__(self, repNums, padding=(0, 0, 0, 0), reflectivity=1.0):
        """
        repNums: a 4-element tuple specifying the number of copies in the up, down,
        left and right direction from the original image in the center.

        padding: the number of black pixels (pixel value = 0) around each image, in
        the up, down, left and right directions. e.g. for padding = (2, 1, 0, 0),
        there are 3 rows of black pixels between adjacent images in the vertical
        direction.

        reflectivity: the intensity attenuation caused by each reflection on the
        mirror. e.g., there is no intensity decrease if reflectivity equals to 1.
        The number of reflection equals the norm-1 distance from the virtual image
        to the original image.
        """

        self.repNums = repNums
        self.padding = padding
        self.reflectivity = reflectivity

    def KaleidoExpan(self, original_image):
        """
        The function returns a torch.tensor 'fullMirror' that is the virtual image
        array generated by a rectangular kaleidoscope around the original image. 

        original_image: the input image is either a PIL image, torch.tensor, or a
        numpy array, and it will be converted to torch.tensor before processed.
        """

        if isinstance(original_image, (PIL.Image.Image,)) or isinstance(original_image, (numpy.ndarray,)):
            im = ToTensor()(original_image)
        elif isinstance(original_image, (torch.Tensor,)):
            im = original_image
            
        im = im.squeeze() # Get rid of dim 0 for color channel.
        (h, w) = im.shape 

        # Pad the surroundings of the image
        pad = self.padding
        repN = self.repNums
        (h, w) = (h + pad[0] + pad[1], w + pad[2] + pad[3])
        im_padded = torch.zeros(h, w)
        im_padded[pad[0]:(h-pad[1]), pad[2]:(w-pad[3])] = im
        im = im_padded

        rowMirror = self.ParaMirrorCavity(im, repN[2:])
        fullMirror = self.ParaMirrorCavity(rowMirror.t(), repN[0:2])

        return fullMirror.t()

    def ParaMirrorCavity(self, padded_image, num_reps):
        """
        The function returns a torch.tensor 'imageRow' that is the virtual image
        array generated by two parallel flat mirrors around the input image
        'original_image'.

        num_reps: a 2-element tuple specifying the number of replication on the
        left and right of the original image. 
        """
        im = padded_image
        (h, w) = im.shape 

        # Create a 3D array to store the row of mirror images of the original image.
        # dim 0: the vertical pixel coordinate of each image; 
        # dim 1: the horizontal position of each mirror image (e.g.,
        # rowMirror[:,0,:] the leftest image, rowMirror[:,repCol,:] the righest).
        # dim 2: the horizontal pixel coordinate of each mirror image. 
        # dim 2 is a sub-dimension of dim 1 so that they are contiguous and can
        # later be binded into one single dimension by torch.tensor.view() 
        imageRow = torch.zeros(h, sum(num_reps)+1, w) # Images are copied in the row direction.

        # The list of image indices to be flipped horizontally. 
        flipIdx = [*range(num_reps[0]-1, -1, -2), *range(num_reps[0]+1, sum(num_reps)+1, 2)] 

        # The list of image indices NOT to be flipped horizontally.
        keepIdx = list(set(range(0, sum(num_reps)+1))-set(flipIdx)) 

        # The tensor encoding attenuation factor of each image in the row
        attenIdx = torch.cat((torch.arange(num_reps[0], 0, -1, dtype=torch.double), torch.arange(0, num_reps[1]+1, dtype=torch.double)))
        attenFactor = self.reflectivity ** attenIdx

        # The flipped version of the image
        imHoriFlip = torch.flip(im, [1])

        # Assign the copies of the flipped image to correct horizontal positions.
        imageRow[:, flipIdx, :] = torch.repeat_interleave(imHoriFlip.unsqueeze(1), len(flipIdx), dim=1)

        # Assign the copies of un-flipped image to correct horizontal positions.
        imageRow[:, keepIdx, :] = torch.repeat_interleave(im.unsqueeze(1), len(keepIdx), dim=1)

        # Apply attenuation coefficient to each of the image copies.
        for i in range(sum(num_reps)+1):
            imageRow[:, i, :] = imageRow[:, i, :] * attenFactor[i]

        # reshape and bind dim 1 to dim 2 (The horizontal position of each mirror image)
        imageRow = imageRow.view(h, -1) 

        return imageRow

    def KaleidoTransform(self, matIn, pxIdx, blkIdx, centerBlk=()):
        """
        The function returns a 2D matrix 'matOut' that is the re-indexed version of
        the input 2D matrix, according to the reflection pattern of a rectangular
        kaleidoscope around the unit block. The unit block is a 2D matrix mapped
        from a row of the input matrix 'matIn', with the pattern instructed by
        'pxIdx'. 'blkIdx' specifies which row is mapped to which block.  

        matIn: a M x N torch.tensor that is to be spatially rearranged.

        pxIdx: a 2D torch.tensor with a total of M elements, that specifies the
        fashion each row of 'matIn' is wrapped into a 2D unit block. The value of
        pxIdx[i][j] indicates the column index of 'matIn' at location [i][j] in the
        unit 2D block in 'matOut'. e.g., pxIdx = [[0,1],[1,2]], maps any given
        element in column 0 of 'matIn' to position [0][0] in the unit block; column
        1 to location [0][1] and [1][0], and column 2 to location [1][1].

        blkIdx: a 2D torch.tensor that specifies which row of the input matrix
        'matIn' appears at which location. The value of blkIdx[i][j] indcates the row
        index of 'matIn' at block index [i][j].   

        centerBlk: a 2-element tuple specifying the central block location of the
        kaleidoscope in blkIdx. The default is empty (), and then the whole blkIdx
        is the center. In this case, the input matrix is spatially rearranged
        without flipping of blocks caused by reflection.
        """
        #assert matIn.shape[1] == pxIdx.shape[0]*pxIdx.shape[1], "The number of elements in pxIdx must match the number of columns in matIn"

        pad = self.padding
        (blk_h, blk_w) = pxIdx.shape
        # number of pixels in each column and row
        (blk_h_pad, blk_w_pad) = (blk_h+sum(pad[0:2]), blk_w+sum(pad[2:])) 

        # number of blocks in each column and row
        (blk_rowCount, blk_colCount) = blkIdx.shape

        # pre-allocate space for the entire image
        transImage = torch.zeros(blk_colCount * blk_w_pad, blk_rowCount, blk_h_pad)
        
        for i in range(0,blk_rowCount):
            # pre-allocate space for each row of image
            transBlkRow = torch.zeros(blk_h_pad, blk_colCount, blk_w_pad)

            for j in range(0, blk_colCount):
                # Reshape the pixel index into a row vector, map each element to
                # their position, and then reshape the row vector back to 2D
                # block.
                linIdx = pxIdx.view(-1,)
                linBlk = torch.take(matIn[blkIdx[i, j], :], linIdx)
                blk2D = linBlk.view(pxIdx.shape)

                if not centerBlk: # no reflection
                    pass
                elif len(centerBlk) == 2:
                    if (i-centerBlk[0])%2 == 1: # the odd index from the original image is reflected
                        blk2D = torch.flip(blk2D, [0])
                    if (j-centerBlk[1])%2 == 1: # the odd index from the original image is reflected
                        blk2D = torch.flip(blk2D, [1])
                    blk2D = blk2D * self.reflectivity ** (abs(i-centerBlk[0])+abs(j-centerBlk[1]))

                # Bind the images in the horizontal direction.
                transBlkRow[pad[0]:pad[0]+blk_h, j, pad[2]:pad[2]+blk_w] = blk2D

            # Bind the rows of images in the vertical direction.
            transImage[:, i, :] = transBlkRow.view(blk_h_pad, -1).t()

        # Reshape the transformed image into a 2D image.
        transImage = transImage.view(blk_colCount * blk_w_pad, -1)        
        return transImage.t()


if __name__ == "__main__":

    dataTr = MNIST('../ML_data/', train=True, download = True)
    kale = Kaleidoscope((1,2,1,1),(2,2,2,2))
    ime = kale.KaleidoExpan(dataTr[0][0])
    ims = ToPILImage()(ime)
    ims.show()

    x = ToTensor()(dataTr[0][0])
    x = x.view(1,-1)
    xForm = kale.KaleidoTransform(x.repeat(6,1), torch.arange(0,784).view(28,-1), torch.arange(0,6).view(2,-1), centerBlk = (0,1) )
    imx = ToPILImage()(xForm)
    #imx.show()



