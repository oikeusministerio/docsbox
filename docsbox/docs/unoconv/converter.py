try:
    import uno
    import unohelper
    from com.sun.star.beans import PropertyValue
    from com.sun.star.io import XOutputStream
except ImportError:
    raise ImportError("Could not find a library.")

import os

from pathlib import Path


class UnoConverter:
    # Stripped down version from https://github.com/unoconv/unoserver/blob/master/src/unoserver/converter.py

    def __init__(self, interface="127.0.0.1", port="2002"):
        print("Starting unoconverter.")

        self.local_context = uno.getComponentContext()
        self.resolver = self.local_context.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", self.local_context
        )
        self.context = self.resolver.resolve(
            f"uno:socket,host={interface},port={port};urp;StarOffice.ComponentContext"
        )
        self.service = self.context.ServiceManager
        self.desktop = self.service.createInstanceWithContext(
            "com.sun.star.frame.Desktop", self.context
        )

    def convert(self, inpath, outfilter, pdf_version, outpath):
        input_props = (PropertyValue(Name="ReadOnly", Value=True),)

        if not Path(inpath).exists():
            raise RuntimeError(f"Path {inpath} does not exist.")

        import_path = uno.systemPathToFileUrl(os.path.abspath(inpath))
        print(f"Opening {inpath}")

        document = self.desktop.loadComponentFromURL(
            import_path, "_default", 0, input_props
        )

        try:
            # https://wiki.openoffice.org/wiki/API/Tutorials/PDF_export
            filter_data = uno.Any("[]com.sun.star.beans.PropertyValue",
                                  tuple([
                                      PropertyValue(Name="SelectPdfVersion", Value=int(pdf_version)),
                                      PropertyValue(Name="ExportFormFields", Value=False),
                                      PropertyValue(Name="ConvertOOoTargetToPDFTarget", Value=True),
                                      PropertyValue(Name="ExportNotes", Value=True),
                                      PropertyValue(Name="FormsType", Value=1),
                                      PropertyValue(Name="MaxImageResolution", Value=300),
                                      PropertyValue(Name="Quality", Value=80),
                                      PropertyValue(Name="ReduceImageResolution", Value=True),
                                      PropertyValue(Name="PDFUACompliance", Value=False),
                                      PropertyValue(Name="UseTaggedPDF", Value=True)
                                  ]))
            output_props = (
                PropertyValue(Name="FilterName", Value=outfilter),
                PropertyValue(Name="FilterData", Value=filter_data),
                PropertyValue(Name="Overwrite", Value=True),
            )
            document.storeToURL(uno.systemPathToFileUrl(os.path.abspath(outpath)), output_props)
        except Exception as e:
            print(repr(e))
        finally:
            document.close(True)
