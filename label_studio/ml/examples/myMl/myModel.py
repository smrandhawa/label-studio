# import pickle
# import os
# import numpy as np
import spacy
import re
# from spacy import displacy
# from sklearn.linear_model import LogisticRegression
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.pipeline import make_pipeline

from label_studio.ml import LabelStudioMLBase


class SimpleTextClassifier(LabelStudioMLBase):

    nlp = None
    dictMap = {
        "ORG": "Organization",
        "PERSON": "Person",
        "LOC": "Location",
        "GPE": "Country/City"
    }

    def __init__(self, **kwargs):
        super(SimpleTextClassifier, self).__init__(**kwargs)
        self.nlp = spacy.load('en_core_web_sm')

    def predict(self, tasks, **kwargs):
        predictions = []
        for task in tasks:
            search =  re.search('.*<Labels name="(.*)" toName="(.*)">.*', task['layout'], re.IGNORECASE)
            # if search:
            from_name = search.group(1)
            to_name = search.group(2)

            sent = task['data'][to_name]
            doc = self.nlp(sent)

            for entity in doc.ents:
                print(entity.text, entity.label_)

                if entity.label_ in self.dictMap:
                    startIndex = sent.index(entity.text)
                    endIndex = startIndex + len(entity.text)

                    result = {
                        'from_name': from_name,
                        'to_name': to_name,
                        'type': 'labels',
                        'value': {'start': startIndex, 'end': endIndex, 'text': entity.text, 'labels': [self.dictMap[entity.label_]]}
                    }
                    predictions.append(result)
                # predictions.append({'result': result, 'score': 100})
            # break

            outData = [{'result': predictions}]
            # displacy.serve(doc, style="ent")
        return outData

    def fit(self, completions, workdir=None, **kwargs):
        return

