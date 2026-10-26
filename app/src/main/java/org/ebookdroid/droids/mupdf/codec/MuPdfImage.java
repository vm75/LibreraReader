package org.ebookdroid.droids.mupdf.codec;

import com.foobnix.pdf.info.Engines;

/** Native image decoding for previews and covers that Android cannot decode. */
public final class MuPdfImage {
    private MuPdfImage() {
    }

    public static boolean isJxl(byte[] data) {
        return data != null && ((data.length >= 2 && (data[0] & 255) == 255 && data[1] == 10)
                || (data.length >= 12 && data[0] == 0 && data[1] == 0 && data[2] == 0 && data[3] == 12
                && data[4] == 'J' && data[5] == 'X' && data[6] == 'L' && data[7] == ' '
                && data[8] == 13 && data[9] == 10 && (data[10] & 255) == 135 && data[11] == 10));
    }

    public static boolean isWebp(byte[] data) {
        return data != null && data.length >= 12 && data[0] == 'R' && data[1] == 'I'
                && data[2] == 'F' && data[3] == 'F' && data[8] == 'W' && data[9] == 'E'
                && data[10] == 'B' && data[11] == 'P';
    }

    /** Returns a PNG preserving transparency and orientation, capped at the requested width. */
    public static byte[] decodeToPng(byte[] data, int width) {
        if (!Engines.IS_MUPDF || (!isJxl(data) && !isWebp(data))) {
            return null;
        }
        NativeLibrary.ensureLoaded();
        return nativeDecodeToPng(data, Math.max(1, width));
    }

    private static final class NativeLibrary {
        static {
            System.loadLibrary(Engines.NATIVE_LIBRARY);
        }

        static void ensureLoaded() {
        }
    }

    private static native byte[] nativeDecodeToPng(byte[] data, int width);
}
