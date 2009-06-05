#------------------------------------------------------------------------------
# Copyright (c) 2005, Enthought, Inc.
# some parts copyright 2002 by Space Telescope Science Institute
# All rights reserved.
# 
# This software is provided without warranty under the terms of the BSD
# license included in enthought/LICENSE.txt and may be redistributed only
# under the conditions described in the aforementioned license.  The license
# is also available online at http://www.enthought.com/licenses/BSD.txt
# Thanks for using Enthought open source!
#------------------------------------------------------------------------------
""" PDF implementation of the core2d drawing library

    :Author:      Eric Jones, Enthought, Inc., eric@enthought.com
    :Copyright:   Space Telescope Science Institute
    :License:     BSD Style

    The PDF implementation relies heavily on the ReportLab project.    
"""
# Major library imports
from itertools import izip
import warnings
import copy
from numpy import array

# ReportLab PDF imports
import reportlab.pdfbase.pdfmetrics
import reportlab.pdfbase._fontdata
from reportlab.pdfgen import canvas

# Local, relative Kiva imports
import basecore2d
import constants
from constants import FILL, STROKE, EOF_FILL
import affine


cap_style = {}
cap_style[constants.CAP_ROUND]  = 1
cap_style[constants.CAP_SQUARE] = 2
cap_style[constants.CAP_BUTT]   = 0

join_style = {}
join_style[constants.JOIN_ROUND] = 1
join_style[constants.JOIN_BEVEL] = 2
join_style[constants.JOIN_MITER] = 0

# stroke, fill, mode
path_mode = {}
path_mode[constants.FILL_STROKE]     = (1,1,canvas.FILL_NON_ZERO)
path_mode[constants.FILL]            = (0,1,canvas.FILL_NON_ZERO)
path_mode[constants.EOF_FILL]        = (0,1,canvas.FILL_EVEN_ODD)
path_mode[constants.STROKE]          = (1,0,canvas.FILL_NON_ZERO)
path_mode[constants.EOF_FILL_STROKE] = (1,1,canvas.FILL_EVEN_ODD)


# fixme: I believe this can be implemented but for now, it is not.
CompiledPath = None

class GraphicsContext(basecore2d.GraphicsContextBase):
    """
    Simple wrapper around a PDF graphics context.
    """ 
    def __init__(self, pdf_canvas):
        self.gc = pdf_canvas
        self.current_pdf_path = None
        self.text_xy = None, None
        basecore2d.GraphicsContextBase.__init__(self)

    #----------------------------------------------------------------
    # Coordinate Transform Matrix Manipulation
    #----------------------------------------------------------------
    
    def scale_ctm(self, sx, sy):
        """
        scale_ctm(sx: float, sy: float) -> None
        
        Sets the coordinate system scale to the given values, (sx,sy).
        """
        self.gc.scale(sx, sy)
        
    def translate_ctm(self, tx, ty):
        """
        translate_ctm(tx: float, ty: float) -> None
        
        Translates the coordinate syetem by the given value by (tx,ty)
        """        
        self.gc.translate(tx, ty)

    def rotate_ctm(self, angle):
        """
        rotate_ctm(angle: float) -> None
        
        Rotates the coordinate space by the given angle (in radians).
        """        
        self.gc.rotate(angle*180/3.14159)
    
    def concat_ctm(self, transform):
        """
        concat_ctm(transform: affine_matrix)
        
        Concatenates the transform to current coordinate transform matrix.
        transform is an affine transformation matrix (see kiva.affine_matrix).
        """
        self.gc.transform(transform)
    
    def get_ctm(self):
        """ Returns the current coordinate transform matrix.  
        
            XXX: This should really return a 3x3 matrix (or maybe an affine
                 object?) like the other API's.  Needs thought.
        """           
        return copy.copy(self.gc._currentMatrix)
        
    #----------------------------------------------------------------
    # Save/Restore graphics state.
    #----------------------------------------------------------------

    def save_state(self):
        """ Saves the current graphic's context state.
       
            Always pair this with a `restore_state()`
        """    
        self.gc.saveState()
    
    def restore_state(self):
        """ Restores the previous graphics state.
        """
        self.gc.restoreState()
                                  
    #----------------------------------------------------------------
    # Manipulate graphics state attributes.
    #----------------------------------------------------------------
    
    def set_should_antialias(self,value):
        """ Sets/Unsets anti-aliasing for bitmap graphics context.
        """
        msg = "antialias is not part of the PDF canvas.  Should it be?"
        raise NotImplementedError, msg
        
    def set_line_width(self,width):
        """ Sets the line width for drawing
        
			Parameters
			----------
            width : float
				The new width for lines in user space units.
        """
        self.gc.setLineWidth(width)

    def set_line_join(self,style):
        """ Sets style for joining lines in a drawing.
            
            style : join_style 
				The line joining style.  The available 
                styles are JOIN_ROUND, JOIN_BEVEL, JOIN_MITER.
        """    
        try:
            sjoin = join_style[style]
        except KeyError:            
            msg = "Invalid line join style.  See documentation for valid styles"
            raise ValueError, msg
        self.gc.setLineJoin(sjoin)
        
    def set_miter_limit(self,limit):
        """ Specifies limits on line lengths for mitering line joins.
        
            If line_join is set to miter joins, the limit specifies which
            line joins should actually be mitered.  If lines aren't mitered,
            they are joined with a bevel.  The line width is divided by
            the length of the miter.  If the result is greater than the
            limit, the bevel style is used.
            
			Parameters
			----------
            limit : float
				limit for mitering joins.            
        """
        self.gc.setMiterLimit(limit)
        
    def set_line_cap(self,style):
        """ Specifies the style of endings to put on line ends.
                  
			Parameters
			----------
            style : cap_style
				the line cap style to use. Available styles 
                are CAP_ROUND, CAP_BUTT, CAP_SQUARE
        """    
        try:
            scap = cap_style[style]
        except KeyError:            
            msg = "Invalid line cap style.  See documentation for valid styles"
            raise ValueError, msg
        self.gc.setLineCap(scap)
       
    def set_line_dash(self,lengths,phase=0):
        """
        	Parameters
			----------
            lengths : float array 
				An array of floating point values 
			    specifing the lengths of on/off painting
			    pattern for lines.
            phase : float
				Specifies how many units into dash pattern
                to start.  phase defaults to 0.
        """
        if basecore2d.is_dashed((phase,lengths)):
            self.gc.setDash(lengths,phase)

    def set_flatness(self,flatness):
        """ 
            
            It is device dependent and therefore not recommended by
            the PDF documentation.
        """    
        msg = "Flatness not implemented yet on PDF"
        raise NotImplementedError, msg

    #----------------------------------------------------------------
    # Sending drawing data to a device
    #----------------------------------------------------------------

    def flush(self):
        """ Sends all drawing data to the destination device.
        
            Currently, this is a NOP.  It used to call ReportLab's save()
            method, and maybe it still should, but flush() is likely to 
            be called a lot, so this will really slow things down.  Also,
            I think save() affects the paging of a document I think.  
            We'll have to look into this more.
        """
        #self.gc.save()
        pass
        
    def synchronize(self):
        """ Prepares drawing data to be updated on a destination device.

            Currently, doesn't do anything.
            Should this call ReportLab's canvas object's showPage() method.
        """
        pass
    
    #----------------------------------------------------------------
    # Page Definitions
    #----------------------------------------------------------------
    
    def begin_page(self):
        """ Creates a new page within the graphics context.

            Currently, this just calls ReportLab's canvas object's
            showPage() method.  Not sure about this...
        """
        self.gc.showPage()
        
    def end_page(self):
        """ Ends drawing in the current page of the graphics context.

            Currently, this just calls ReportLab's canvas object's
            showPage() method.  Not sure about this...
        """        
        self.gc.showPage()        
    
    #----------------------------------------------------------------
    # Building paths (contours that are drawn)
    #
    # + Currently, nothing is drawn as the path is built.  Instead, the
    #   instructions are stored and later drawn.  Should this be changed?
    #   We will likely draw to a buffer instead of directly to the canvas
    #   anyway.
    #   
    #   Hmmm. No.  We have to keep the path around for storing as a 
    #   clipping region and things like that.
    #
    # + I think we should keep the current_path_point hanging around.
    #
    #----------------------------------------------------------------
            
    def begin_path(self):
        """ Clears the current drawing path and begins a new one.
        """
        self.current_pdf_path = self.gc.beginPath()

    def move_to(self,x,y):    
        """ Starts a new drawing subpath at place the current point at (x,y).
        """
        if self.current_pdf_path is None:
            self.begin_path()
        self.current_pdf_path.moveTo(x,y)
        
    def line_to(self,x,y):
        """ Adds a line from the current point to the given point (x,y).
        
            The current point is moved to (x,y).
        """
        self.current_pdf_path.lineTo(x,y)
            
    def lines(self,points):
        """ Adds a series of lines as a new subpath.  
        
            Currently implemented by calling line_to a zillion times.
        
            Points is an Nx2 array of x,y pairs.
            
            current_point is moved to the last point in points           
        """
        self.current_pdf_path.moveTo(points[0][0],points[0][1])
        for x,y in points[1:]:
            self.current_pdf_path.lineTo(x,y)

    def line_set(self, starts, ends):
        for start, end in izip(starts, ends):
            self.current_pdf_path.moveTo(start[0], start[1])
            self.current_pdf_path.lineTo(end[0], end[1])
                
    def rect(self, *args):
        """ Adds a rectangle as a new subpath.  Can be called in two ways:
              rect(x, y, w, h)
              rect( (x,y,w,h) )
              
        """
        if self.current_pdf_path is None:
            self.begin_path()
        if len(args) == 1:
            args = args[0]
        self.current_pdf_path.rect(*args)
    
    def draw_rect(self, rect, mode=constants.FILL_STROKE):
        self.rect(rect)
        stroke, fill, mode = path_mode[mode]
        self.draw_path(mode)

    def rects(self,rects):
        """ Adds multiple rectangles as separate subpaths to the path.
        
            Currently implemented by calling rect a zillion times.
                   
        """
        for x,y,sx,sy in rects:
            self.current_pdf_path.rect(x,y,sx,sy)
        
    def close_path(self):
        """ Closes the path of the current subpath.
        """
        self.current_pdf_path.close()

    def curve_to(self, cp1x, cp1y, cp2x, cp2y, x, y):
        """ 
        """
        self.current_pdf_path.curveTo(cp1x, cp1y, cp2x, cp2y, x, y)
        
    def quad_curve_to(self,cpx,cpy,x,y):
        """
        """
        msg = "quad curve to not implemented yet on PDF"
        raise NotImplementedError, msg
    
    def arc(self, x, y, radius, start_angle, end_angle, clockwise):
        """
        """
        self.current_pdf_path.arc(x, y, radius, start_angle, end_angle, 
                                  clockwise)
    
    def arc_to(self, x1, y1, x2, y2, radius):
        """
        """
        self.current_pdf_path.arcTo(x1, y1, x2, y2, radius)
                                           
    #----------------------------------------------------------------
    # Getting infomration on paths
    #----------------------------------------------------------------

    def is_path_empty(self):
        """ Tests to see whether the current drawing path is empty
        """
        msg = "is_path_empty not implemented yet on PDF"
        raise NotImplementedError, msg
        
    def get_path_current_point(self):
        """ Returns the current point from the graphics context.
        
            Note: This should be a tuple or array.
        
        """
        msg = "get_path_current_point not implemented yet on PDF"
        raise NotImplementedError, msg
            
    def get_path_bounding_box(self):
        """
            Should return a tuple or array instead of a strange object.
        """
        msg = "get_path_bounding_box not implemented yet on PDF"
        raise NotImplementedError, msg

    #----------------------------------------------------------------
    # Clipping path manipulation
    #----------------------------------------------------------------

    def clip(self):
        """
        """
        self.gc._fillMode = canvas.FILL_NON_ZERO
        self.gc.clipPath(self.current_pdf_path, stroke=0, fill=0)
        
    def even_odd_clip(self):
        """
        """
        self.gc._fillMode = canvas.FILL_EVEN_ODD
        self.gc.clipPath(self.current_pdf_path, stroke=0, fill=1)
        
    def clip_to_rect(self,x,y,width,height):
        """ Clips context to the given rectangular region.
        
            Region should be a 4-tuple or a sequence.            
        """
        return

        
        #probably doesn't work until translate between the matrices
        #a,b,c,d,tx,ty=self.get_ctm()
        #newctm=affine.affine_from_values(a,b,c,d,tx,ty)
  #      newpos=affine.transform_point(newctm,(x,y))
        #self.save_state()
        self.begin_path()
        self.current_pdf_path.rect(x,y,width,height)
        #temppath=copy.copy(self.current_pdf_path)
        #self.restore_state()
        #self.gc._fillMode = canvas.FILL_NON_ZERO
        self.gc.clipPath(self.current_pdf_path, stroke=0, fill=0)
        self.stroke_path()


        
    def clip_to_rects(self):
        """
        """
        msg = "clip_to_rects not implemented yet on PDF."
        raise NotImplementedError, msg
        
    def clear_clip_path ( self ):
        """
        """

        return
        self.clip_to_rect(0,0,10000,10000)
#       msg = "clear_clip_path not implemented yet on PDF"
#       raise NotImplementedError, msg
        
    #----------------------------------------------------------------
    # Color space manipulation
    #
    # I'm not sure we'll mess with these at all.  They seem to
    # be for setting the color syetem.  Hard coding to RGB or
    # RGBA for now sounds like a reasonable solution.
    #----------------------------------------------------------------

    def set_fill_color_space(self):
        """
        """
        msg = "set_fill_color_space not implemented on PDF yet."
        raise NotImplementedError, msg
    
    def set_stroke_color_space(self):
        """
        """
        msg = "set_stroke_color_space not implemented on PDF yet."
        raise NotImplementedError, msg
        
    def set_rendering_intent(self):
        """
        """
        msg = "set_rendering_intent not implemented on PDF yet."
        raise NotImplementedError, msg
        
    #----------------------------------------------------------------
    # Color manipulation
    #----------------------------------------------------------------

    def set_fill_color(self,color):
        """ PDF currently ignores the alpha value        
        """
        r,g,b = color[:3]
        try:
            a = color[3]
        except IndexError:
            a = 1.0
        self.gc.setFillColorRGB(r, g, b)
    
    def set_stroke_color(self,color):
        """ PDF currently ignores the alpha value
        """
        r,g,b = color[:3]
        try:
            a = color[3]
        except IndexError:
            a = 1.0
        self.gc.setStrokeColorRGB(r, g, b)
    
    def set_alpha(self, alpha):
        """
        """
        msg = "set_alpha not implemented on PDF yet."
        raise NotImplementedError, msg
    
    #def set_gray_fill_color(self):
    #    """
    #    """
    #    pass
    
    #def set_gray_stroke_color(self):
    #    """
    #    """
    #    pass
        
    #def set_rgb_fill_color(self):
    #    """
    #    """
    #    pass
        
    #def set_rgb_stroke_color(self):
    #    """
    #    """
    #    pass
    
    #def cmyk_fill_color(self):
    #    """
    #    """
    #    pass
    
    #def cmyk_stroke_color(self):
    #    """
    #    """
    #    pass
                        
    #----------------------------------------------------------------
    # Drawing Images
    #----------------------------------------------------------------
        
    def draw_image(self, img, rect=None):
        """
        draw_image(img_gc, rect=(x,y,w,h))
        
        Draws another gc into this one.  If 'rect' is not provided, then
        the image gc is drawn into this one, rooted at (0,0) and at full
        pixel size.  If 'rect' is provided, then the image is resized
        into the (w,h) given and drawn into this GC at point (x,y).
        
        img_gc is either a Numeric array (WxHx3 or WxHx4) or a GC from Kiva's
        Agg backend (kiva.agg.GraphicsContextArray).
        
        Requires the Python Imaging Library (PIL).
        """
        
        
        # We turn img into a PIL object, since that is what ReportLab
        # requires.  To do this, we first determine if the input image
        # GC needs to be converted to RGBA/RGB.  If so, we see if we can
        # do it nicely (using convert_pixel_format), and if not, we do
        # it brute-force using Agg.
        
        import Image as PilImage
        from enthought.kiva import agg

        if type(img) == type(array([])):
            # Numeric array
            converted_img = agg.GraphicsContextArray(img, pix_format='rgba32')
            format = 'RGBA'
        elif isinstance(img, agg.GraphicsContextArray):
            if img.format().startswith('RGBA'):
                format = 'RGBA'
            elif img.format().startswith('RGB'):
                format = 'RGB'
            else:
                converted_img = img.convert_pixel_format('rgba32', inplace=0)
                format = 'RGBA'
        else:
            warnings.warn("Cannot render image of type '%r' into PDF context." % \
                    type(img))
            return
        
        # converted_img now holds an Agg graphics context with the image
        pil_img = PilImage.new(format, (converted_img.width(),
                                        converted_img.height()))
        
        if rect == None:
            rect = (0, 0, img.width(), img.height())
        
        # draw the actual image.
        self.gc.drawImage(pil_img, rect[0], rect[1], rect[2], rect[3])
    
    #----------------------------------------------------------------
    # Drawing PDF documents
    #----------------------------------------------------------------

    #def draw_pdf_document(self):
    #    """
    #    """
    #    pass    

    #----------------------------------------------------------------
    # Drawing Text
    #----------------------------------------------------------------
    
    def select_font(self, name, size, textEncoding):
        """ PDF ignores the Encoding variable.
        """
        self.gc.setFont(name,size)

    def set_font(self, font):
        """ Sets the font for the current graphics context.
        """
        # TODO: Make this actually do the right thing
        if font.face_name == "":
            font.face_name = "Helvetica"
        self.gc.setFont(font.face_name,font.size)
    
    def set_font_size(self,size):
        """
        """
        font = self.gc._fontname
        self.gc.setFont(font,size)
        
    def set_character_spacing(self):
        """
        """
        pass
            
    def set_text_drawing_mode(self):
        """
        """
        pass
    
    def set_text_position(self,x,y):
        """
        """
        self.text_xy = x, y
        
    def get_text_position(self):
        """
        """
        return self.state.text_matrix[2,:2]
        
    def set_text_matrix(self,ttm):
        """
        """
        a,b,c,d,tx,ty=affine.affine_params(ttm)
        #print "set text matrix", a,b,c,d,tx,ty
        self.gc._textMatrix=(a,b,c,d,tx,ty)
        #self.gc.CGContextGetTextMatrix(ttm)
        
    def get_text_matrix(self):
        """
            temporarily not implemented.  can perhaps get the _textmatrix object off
            of the canvas if we need to.
        """        
        a,b,c,d,tx,ty= self.gc._textMatrix
        #print "get text matrix", a,b,c,d,tx,ty
        return affine.affine_from_values(a,b,c,d,tx,ty)
        #self.gc.CGContextGetTextMatrix(self.gc)
        
    def show_text(self, text, x = None, y = None):
        """ Draws text on the device at current text position.
            
            This is also used for showing text at a particular point
            specified by x and y.
            
            This ignores the text matrix for now.
        """
        if x and y:
            pass
        else:
            x,y = self.text_xy                       
        self.gc.drawString(x,y,text)

    def show_text_at_point(self, text, x, y):
        self.show_text(text, x, y)
        
    def show_glyphs(self):
        """
        """
        msg = "show_glyphs not implemented on PDF yet."
        raise NotImplementedError, msg
        

    def get_full_text_extent(self,textstring):
        fontname=self.gc._fontname
        fontsize=self.gc._fontsize
        
        #this call does not seem to work. returns zero
        #ascent=(reportlab.pdfbase.pdfmetrics.getFont(fontname).face.ascent)       
        #this call does not seem to work. returns -1
        #descent=(reportlab.pdfbase.pdfmetrics.getFont(fontname).face.descent)

        ascent,descent=reportlab.pdfbase._fontdata.ascent_descent[fontname]
        #print "ascent", ascent, "descent",descent
        descent = (-descent) * fontsize / 1000.0
        ascent = ascent * fontsize / 1000.0
        #print "ascent", ascent, "descent",descent
        height=ascent+descent
        width=self.gc.stringWidth(textstring,fontname,fontsize)
        #the final return value is defined as leading. do not know
        #how to get that number so returning zero
        return width, height ,descent, 0 



    def get_text_extent(self,textstring):
        w,h,d,l = self.get_full_text_extent(textstring)
        return w,h
        
     
        
    
    #----------------------------------------------------------------
    # Painting paths (drawing and filling contours)
    #----------------------------------------------------------------

    def stroke_path(self):
        """
        """
        self.draw_path(mode=STROKE)
    
    def fill_path(self):
        """
        """
        self.draw_path(mode=FILL)
        
    def eof_fill_path(self):
        """
        """
        self.draw_path(mode=EOF_FILL)

    def stroke_rect(self,rect):
        """
        """
        self.begin_path()
        self.rect(rect[0],rect[1],rect[2],rect[3])
        self.stroke_path()
    
    def stroke_rect_with_width(self,rect,width):
        """
        """
        msg = "stroke_rect_with_width not implemented on PDF yet."
        raise NotImplementedError, msg

    def fill_rect(self,rect):
        """
        """
        self.begin_path()
        self.rect(rect[0],rect[1],rect[2],rect[3])
        self.fill_path()
        
    def fill_rects(self):
        """
        """
        msg = "fill_rects not implemented on PDF yet."
        raise NotImplementedError, msg
    
    def clear_rect(self,rect):
        """
        """
        msg = "clear_rect not implemented on PDF yet."
        raise NotImplementedError, msg
            
    def draw_path(self,mode=constants.FILL_STROKE):
        """ Walks through all the drawing subpaths and draw each element.
        
            Each subpath is drawn separately.
        """
        if self.current_pdf_path is not None:    
            stroke,fill,mode = path_mode[mode]
            self.gc._fillMode = mode
            self.gc.drawPath(self.current_pdf_path,stroke=stroke,fill=fill)
            # erase the current path.
            self.current_pdf_path = None
    
    def save(self):
        self.gc.save()

# Arbitrary size not working.
class Canvas:
    def __init__(self,filename,size=(612,792)):
        pdf_canvas = canvas.Canvas(filename)
        self.gc = GraphicsContext(pdf_canvas)
        self._size = size
        
    def draw(self,region=None):
        """ Implement this in your derived class to draw in on the 
            Canvas.            
        """
        pass
    
    def size(self):
        # Hard coded to a letter sized paper for now:
        return self._size
        
    def save(self):
        """ Saves the drawing to disk.
        """
        self.gc.gc.save()


# for testing...
class CanvasWindow:
    pass

def simple_test():
    pdf = canvas.Canvas("bob.pdf")
    gc = GraphicsContext(pdf)
    gc.begin_path()
    gc.move_to(50,50)
    gc.line_to(100,100)
    gc.draw_path()
    gc.flush()
    pdf.save()
    
def show_all_samplers(doc_title = 'pdf_samples'):        
    """ This is hacked so that all samples are put on the same page
    """
    #-------------------------------------------------------------------------
    # Force use of pdf as the core2d backend.
    #-------------------------------------------------------------------------
    import os
    os.environ['KIVA_WISHLIST'] = 'pdf'
    import core2d
    reload(core2d)
    import sampler 
    reload(sampler)
       
    gc = None
    for title,samples in sampler.all_samples:
        w = sampler.SamplerCanvas(doc_title+'.pdf')#,size=default_size)
        if gc:
            w.gc = gc
        else:
            gc = w.gc
        # commented out for now because it causes blank pages.
        #w.gc.begin_page()
        w.set_samplers(samples)
        w.do_draw(w.gc)
        w.gc.end_page()
    w.save()

if __name__ == "__main__":
    #show_all_samplers()
    import sys
    if len(sys.argv) == 1:
        print "Usage: %s output_file" % sys.argv[0]
        raise SystemExit
    
