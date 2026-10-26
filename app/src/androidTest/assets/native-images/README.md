# Native image fixtures

These small WebP and JPEG XL fixtures come from the embedded byte arrays in
`source/tests/test-webp.c` and `source/tests/test-jxl.c` of vm75/mupdf revision
`71047a69f3a24b4e002a7ac5e97680595bec818d` (AGPL-3.0).

They cover RGB, partial and full transparency, JPEG XL orientation and 16-bit
grayscale. `Builder/tests/NativeImageSmoke.java` exercises the production JNI
bridge against them on a host JVM.
